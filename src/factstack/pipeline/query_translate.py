"""Query translation for cross-lingual retrieval in FactStack."""

import re
from typing import Optional, Literal

from factstack.llm.base import BaseLLM


# Simple Chinese-English dictionary for rule-based translation fallback
ZH_EN_DICT = {
    # Common technical terms
    "如何": "how to",
    "怎么": "how to",
    "什么": "what",
    "为什么": "why",
    "哪里": "where",
    "回滚": "rollback",
    "部署": "deploy deployment",
    "服务": "service",
    "配置": "configure configuration",
    "问题": "issue problem",
    "错误": "error",
    "故障": "failure fault",
    "排查": "troubleshoot debug",
    "调试": "debug",
    "日志": "log logs",
    "查看": "view check",
    "检查": "check verify",
    "重启": "restart",
    "启动": "start",
    "停止": "stop",
    "连接": "connection connect",
    "数据库": "database",
    "内存": "memory",
    "网络": "network",
    "延迟": "latency delay",
    "性能": "performance",
    "监控": "monitoring monitor",
    "告警": "alert alarm",
    "事件": "incident event",
    "响应": "response",
    "处理": "handle process",
    "容器": "container",
    "集群": "cluster",
    "节点": "node",
    "状态": "status state",
    "健康": "health healthy",
    "探针": "probe",
    "流量": "traffic",
    "负载": "load",
    "均衡": "balance balancer",
    "扩容": "scale scaling",
    "缩容": "scale down",
    "发布": "release publish",
    "版本": "version",
    "更新": "update",
    "升级": "upgrade",
    "降级": "downgrade",
    "镜像": "image",
    "拉取": "pull",
    "推送": "push",
    "命令": "command",
    "执行": "execute run",
    "步骤": "step steps procedure",
    "设置": "setting settings",
    "参数": "parameter",
    "阈值": "threshold",
    "超时": "timeout",
    "重试": "retry",
    "池": "pool",
    "泄漏": "leak",
    "溢出": "overflow",
    "崩溃": "crash",
    "挂起": "hang",
    "死锁": "deadlock",
    "队列": "queue",
    "缓存": "cache",
    "清理": "clean clear",
}


def translate_rule_based(query: str) -> str:
    """Translate a Chinese query to English using rule-based dictionary.
    
    This is a fallback method when LLM is not available.
    
    Args:
        query: Chinese query string
    
    Returns:
        English translation (best effort)
    """
    result_words = []
    remaining = query
    
    # Try to match longer phrases first
    sorted_dict = sorted(ZH_EN_DICT.items(), key=lambda x: len(x[0]), reverse=True)
    
    while remaining:
        matched = False
        for zh, en in sorted_dict:
            if remaining.startswith(zh):
                result_words.append(en)
                remaining = remaining[len(zh):]
                matched = True
                break
        
        if not matched:
            # Skip one character if no match
            char = remaining[0]
            # If it's an ASCII character or number, keep it
            if char.isascii() and (char.isalnum() or char in "?!.,"):
                result_words.append(char)
            remaining = remaining[1:]
    
    # Clean up and join
    result = " ".join(result_words)
    # Remove extra spaces and clean up
    result = re.sub(r'\s+', ' ', result).strip()
    return result if result else query


def translate_with_llm(query: str, llm: BaseLLM) -> str:
    """Translate a query using LLM for retrieval-friendly English.
    
    Args:
        query: Query string to translate
        llm: LLM instance for translation
    
    Returns:
        Translated query optimized for retrieval
    """
    try:
        # Check if the LLM has a translate method
        if hasattr(llm, 'translate_query'):
            return llm.translate_query(query)
        
        # Use rewrite_query with a translation-focused approach
        # For DummyLLM, this will fall back to basic keyword extraction
        translated = llm.rewrite_query(f"Translate to English keywords: {query}")
        
        # If result still contains CJK, use rule-based fallback
        from factstack.pipeline.query_language import count_cjk_chars
        if count_cjk_chars(translated) > 0:
            return translate_rule_based(query)
        
        return translated
    except Exception:
        # Fallback to rule-based translation
        return translate_rule_based(query)


class QueryTranslator:
    """Handles query translation for cross-lingual retrieval."""
    
    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        mode: Literal["llm", "rule", "off"] = "llm"
    ):
        """Initialize query translator.
        
        Args:
            llm: Optional LLM instance for translation
            mode: Translation mode - "llm", "rule", or "off"
        """
        self.llm = llm
        self.mode = mode
    
    def translate_for_retrieval(
        self,
        query: str,
        src_lang: str = "zh"
    ) -> Optional[str]:
        """Translate a query to English for retrieval.
        
        Args:
            query: Original query
            src_lang: Source language ("zh", "en", "mixed")
        
        Returns:
            Translated query, or None if translation is off or not needed
        """
        if self.mode == "off":
            return None
        
        if src_lang == "en":
            return None  # No translation needed
        
        if self.mode == "llm" and self.llm is not None:
            return translate_with_llm(query, self.llm)
        else:
            # Rule-based fallback
            return translate_rule_based(query)
    
    def get_mode_info(self) -> str:
        """Get information about the current translation mode."""
        if self.mode == "off":
            return "off"
        elif self.mode == "llm" and self.llm is not None:
            return "llm"
        else:
            return "rule"
