"""Pipeline tuning knobs read from environment; invalid values must fail loudly.

MAX_REVISIONS：允许的额外修订轮数（不含首次生成），合法范围仅 0 或 1。
- 缺省 1：保持原有行为（第一轮失败后允许一次修订，累计最多 4 次模型调用）。
- 0：只执行一次生成与一次独立核验，任何失败立即按原有失败机制返回，不调用 revise。
- 其他值（2、3、100、负数等）一律拒绝，在构造 QAService（即服务启动）时明确报错，不静默回退。
"""
import os


class ConfigError(ValueError):
    """Raised for invalid configuration; startup must abort instead of guessing."""


def validate_max_revisions(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f'MAX_REVISIONS 必须是整数 0 或 1，当前值: {value!r}')
    if value not in (0, 1):
        raise ConfigError(
            f'MAX_REVISIONS 仅允许 0 或 1（0=不修订，1=最多一次修订），当前值: {value}')
    return value


def max_revisions_from_env(environ=None) -> int:
    env = os.environ if environ is None else environ
    raw = env.get('MAX_REVISIONS', '1')
    try:
        value = int(raw.strip())
    except (AttributeError, ValueError):
        raise ConfigError(
            f'MAX_REVISIONS 仅允许 0 或 1，当前值: {raw!r}') from None
    return validate_max_revisions(value)
