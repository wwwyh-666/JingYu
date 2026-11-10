"""Small configurable Chat Completions adapter; no SDK or hidden retries."""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import json
import os
from time import perf_counter
from urllib.parse import urlsplit

import httpx
from .models import CallRecord


def timestamp() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


class ModelError(Exception):
    def __init__(self, code: str, record: CallRecord):
        super().__init__(code)  # Never include provider error bodies or headers.
        self.code = code
        self.record = record


@dataclass
class ModelConfig:
    provider: str = 'disabled'
    model: str = ''
    base_url: str = ''
    api_key: str = field(default='', repr=False)
    timeout_seconds: float = 30
    max_tokens: int = 1600

    @classmethod
    def from_env(cls):
        provider = os.getenv('MODEL_PROVIDER', 'disabled').strip()
        try:
            timeout=float(os.getenv('MODEL_TIMEOUT_SECONDS','30'))
            max_tokens=int(os.getenv('MODEL_MAX_OUTPUT_TOKENS','1600'))
        except ValueError:
            timeout=0
            max_tokens=0
        return cls(provider=provider, model=os.getenv('MODEL_NAME','').strip(),
            base_url=os.getenv('MODEL_BASE_URL', 'https://api.deepseek.com' if provider=='deepseek' else '').strip().rstrip('/'),
            api_key=os.getenv('MODEL_API_KEY',''),
            timeout_seconds=timeout,max_tokens=max_tokens)

    def missing(self) -> list[str]:
        missing=[]
        if self.provider not in {'deepseek','openai_compatible'}: missing.append('MODEL_PROVIDER')
        for name,value in [('MODEL_NAME',self.model),('MODEL_BASE_URL',self.base_url),('MODEL_API_KEY',self.api_key)]:
            if not value.strip(): missing.append(name)
        try:
            parts=urlsplit(self.base_url)
        except ValueError:
            return missing+['MODEL_BASE_URL_INVALID']
        local_http=parts.scheme=='http' and parts.hostname in {'127.0.0.1','localhost','::1'}
        if self.base_url and (not (parts.scheme=='https' or local_http) or not parts.hostname
                              or parts.username or parts.password or parts.query or parts.fragment):
            missing.append('MODEL_BASE_URL_INVALID')
        if not 1 <= self.timeout_seconds <= 120: missing.append('MODEL_TIMEOUT_SECONDS_INVALID')
        if not 100 <= self.max_tokens <= 8000: missing.append('MODEL_MAX_OUTPUT_TOKENS_INVALID')
        return missing


def numeric_usage(value):
    """Keep the provider's actual numeric usage, including nested token details."""
    if isinstance(value, dict):
        return {str(k):numeric_usage(v) for k,v in value.items() if isinstance(v,(dict,int,float)) and not isinstance(v,bool)}
    return value


class ChatModel:
    simulated = False

    def __init__(self, config: ModelConfig, transport=None):
        self.config = config
        self.transport = transport

    @property
    def ready(self):
        return not self.config.missing()

    def complete(self, phase: str, system: str, payload: dict):
        started=timestamp()
        t0=perf_counter()
        record=CallRecord(phase=phase,started_at=started,elapsed_ms=0,
                          configured_model=self.config.model or None,status='not_called')
        if not self.ready:
            record.error_code='MODEL_NOT_CONFIGURED'
            raise ModelError('MODEL_NOT_CONFIGURED',record)
        body={'model':self.config.model,'messages':[
            {'role':'system','content':system},
            {'role':'user','content':json.dumps(payload,ensure_ascii=False)}],
            'response_format':{'type':'json_object'},'stream':False,'max_tokens':self.config.max_tokens,
            'temperature':0}
        if self.config.provider=='deepseek':
            body['thinking']={'type':'disabled'}
        try:
            record.status='attempted'
            with httpx.Client(timeout=self.config.timeout_seconds,trust_env=False,
                              transport=self.transport,follow_redirects=False) as client:
                response=client.post(self.config.base_url+'/chat/completions',json=body,
                    headers={'Authorization':'Bearer '+self.config.api_key,'Content-Type':'application/json'})
            if response.status_code >= 300:
                raise ValueError('MODEL_HTTP_'+str(response.status_code))
            raw=response.json()
            if not isinstance(raw,dict): raise ValueError('MODEL_INVALID_RESPONSE')
            actual=raw.get('model')
            if not isinstance(actual,str) or not actual.strip():
                raise ValueError('MODEL_RESPONSE_MISSING_MODEL')
            record.actual_model=actual
            record.usage=numeric_usage(raw.get('usage',{})) if isinstance(raw.get('usage',{}),dict) else {}
            choice=raw['choices'][0]
            if not isinstance(choice,dict): raise ValueError('MODEL_INVALID_RESPONSE')
            if choice.get('finish_reason')!='stop':
                raise ValueError('MODEL_INCOMPLETE_OUTPUT')
            # Never pass reasoning_content to another request or to logs.
            content=choice['message']['content']
            if not isinstance(content,str) or not content.strip():
                raise ValueError('MODEL_EMPTY_OUTPUT')
            result=json.loads(content)
            if not isinstance(result,dict): raise ValueError('MODEL_INVALID_JSON_OBJECT')
            record.status='success'
            record.elapsed_ms=round((perf_counter()-t0)*1000,3)
            return result,record
        except httpx.TimeoutException:
            code='MODEL_TIMEOUT'
        except httpx.TransportError:
            code='MODEL_TRANSPORT_ERROR'
        except (ValueError,KeyError,IndexError,TypeError) as exc:
            msg=str(exc)
            code=msg if msg.startswith('MODEL_') and len(msg)<80 else 'MODEL_INVALID_RESPONSE'
        record.status='failed'
        record.elapsed_ms=round((perf_counter()-t0)*1000,3)
        record.error_code=code
        raise ModelError(code,record)
