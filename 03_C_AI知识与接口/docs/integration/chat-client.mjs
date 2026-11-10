// Browser ES module. Importing this file does not send any request.
// No automatic retry: each /chat call can trigger paid model requests on the server.
export async function askJingyu({
  baseUrl = 'http://127.0.0.1:8000',
  question = '祈年殿的蓝瓦是什么时候改的？',
  spotId = 'TT', objectId = 'TT_QND', signal,
} = {}) {
  const requestId = globalThis.crypto?.randomUUID?.()
    ?? `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const request = { spot_id: spotId, object_id: objectId, question, request_id: requestId };
  const response = await fetch(`${baseUrl.replace(/\/$/, '')}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'omit',
    body: JSON.stringify(request),
    signal,
  });
  let body;
  try { body = await response.json(); }
  catch {
    throw Object.assign(new Error('后端未返回有效 JSON，请检查服务或代理。'),
      { code: 'CLIENT_INVALID_JSON', httpStatus: response.status });
  }
  if (!response.ok) {
    const code = body?.error_code ?? body?.detail?.code ?? `HTTP_${response.status}`;
    const message = typeof body?.answer === 'string' ? body.answer
      : response.status === 422 ? '请求参数不符合接口要求。'
      : '问答请求未完成，请检查错误状态。';
    throw Object.assign(new Error(message), { code, httpStatus: response.status, body });
  }
  if (!body || body.request_id !== requestId || body.spot_id !== spotId
      || typeof body.answer !== 'string') {
    throw Object.assign(new Error('返回结构或请求标识不匹配，停止播报。'),
      { code: 'CLIENT_RESPONSE_MISMATCH', body });
  }
  const canSpeak = body.error_code === null && body.is_mock === false
    && body.model_called === true && body.check_status === 'passed'
    && body.confidence_flag === 'supported'
    && body.evidence_review_status === 'approved'
    && body.verification?.status === 'supported'
    && Array.isArray(body.claims) && body.claims.length > 0
    && Array.isArray(body.fact_ids) && body.fact_ids.length > 0
    && Array.isArray(body.citations) && body.citations.length > 0
    && Array.isArray(body.evidence) && body.evidence.length > 0;
  return {
    requestId, displayText: body.answer,
    speechText: canSpeak ? body.answer : null,
    canSpeak, response: body,
  };
}

export async function getSource(baseUrl, sourceId, { signal } = {}) {
  const response = await fetch(
    `${baseUrl.replace(/\/$/, '')}/sources/${encodeURIComponent(sourceId)}`,
    { method: 'GET', credentials: 'omit', signal },
  );
  const body = await response.json();
  if (!response.ok) throw Object.assign(new Error('来源当前不可查看。'),
    { code: body?.detail?.code ?? `HTTP_${response.status}`, body });
  return body;
}
