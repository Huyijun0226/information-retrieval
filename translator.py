from abc import ABC, abstractmethod

import re

def parse_input(text):
    """将文本解析为有效词汇列表，支持换行、逗号、分号、顿号分隔"""
    if not text:
        return []
    # 使用正则表达式匹配多种分隔符：换行 \n, 英文逗号 ,, 中文逗号 ，, 英文分号 ;, 中文分号 ；, 顿号 、
    # 同时过滤掉空字符串
    raw_words = re.split(r'[\n,，;；、]', text)
    return [w.strip() for w in raw_words if w.strip()]

class BaseTranslator(ABC):
    """转译策略基类"""
    @abstractmethod
    def translate(self, valid_groups, start_year, end_year):
        pass

    def validate_query(self, query):
        """通用语法校验：检查括号和引号是否成对"""
        errors = []
        if query.count('(') != query.count(')'):
            errors.append("括号未闭合")
        if query.count('"') % 2 != 0:
            errors.append("双引号未闭合")
        if query.count("'") % 2 != 0:
            errors.append("单引号未闭合")
        
        return errors

class CNKITranslator(BaseTranslator):
    """CNKI (知网) 转译策略"""
    def translate(self, valid_groups, start_year, end_year):
        # CNKI规则：TKA=('w1'+'w2')*('w3'+'w4') AND YE>=2019 AND YE<=2026
        # 组内+，组间*。不能有通配符*和?
        cnki_groups = []
        for g in valid_groups:
            # 清理非法通配符
            cleaned = [w.replace('*', '').replace('?', '') for w in g]
            # CNKI中一般短语不需要双引号，用单引号包裹即可
            cnki_groups.append("(" + "+".join(f"'{w}'" for w in cleaned) + ")")
        query = "TKA=" + "*".join(cnki_groups)
        if start_year: query += f" AND YE>={start_year}"
        if end_year: query += f" AND YE<={end_year}"
        
        errors = self.validate_query(query)
        note = "✅ CNKI已自动清理了输入中的 `*` 和 `?` 通配符以防止语法错误。短语使用了单引号包裹。"
        if errors:
            note = "❌ 语法校验异常：" + "，".join(errors) + "。"
            
        return {
            "query": query, 
            "note": note
        }

class WoSTranslator(BaseTranslator):
    """Web of Science 转译策略"""
    def translate(self, valid_groups, start_year, end_year):
        # WoS规则：TS=("w1" OR w2) AND TS=(w3) AND PY=2019-2026
        wos_groups = []
        for g in valid_groups:
            # 带有空格或连字符的英文短语加双引号
            cleaned = [f'"{w}"' if (' ' in w or '-' in w) and not w.startswith('"') else w for w in g]
            wos_groups.append("TS=(" + " OR ".join(cleaned) + ")")
        query = " AND ".join(wos_groups)
        if start_year and end_year: 
            query += f" AND PY={start_year}-{end_year}"
            
        errors = self.validate_query(query)
        note = "✅ 已为带有空格或连字符的英文短语自动添加双引号。"
        if errors:
            note = "❌ 语法校验异常：" + "，".join(errors) + "。"

        return {
            "query": query, 
            "note": note
        }

class IEEETranslator(BaseTranslator):
    """IEEE Xplore 转译策略"""
    def translate(self, valid_groups, start_year, end_year):
        # IEEE规则：("w1" OR w2) AND (w3) （年份在侧边栏筛选，不在式子中）
        ieee_groups = []
        for g in valid_groups:
            cleaned = [f'"{w}"' if (' ' in w or '-' in w) and not w.startswith('"') else w for w in g]
            ieee_groups.append("(" + " OR ".join(cleaned) + ")")
        query = " AND ".join(ieee_groups)
        
        errors = self.validate_query(query)
        note = "⚠️ 注意：请在 IEEE 检索结果页使用侧边栏 Year Range 勾选年份，检索式内不支持直接写年份。"
        if errors:
            note = "❌ 语法校验异常：" + "，".join(errors) + "。"
            
        return {
            "query": query, 
            "note": note
        }

class CXTranslator(BaseTranslator):
    """超星发现 转译策略"""
    def translate(self, valid_groups, start_year, end_year):
        # 超星规则：Su=("w1"|w2)*("w3"|w4) AND Y=2019|2020|...
        cx_groups = []
        for g in valid_groups:
            cleaned = [f'"{w}"' if (' ' in w or '-' in w) and not w.startswith('"') else w for w in g]
            cx_groups.append("(" + "|".join(cleaned) + ")")
        query = "Su=" + "*".join(cx_groups)
        if start_year and end_year:
            years = [str(y) for y in range(int(start_year), int(end_year) + 1)]
            query += f" AND Y={'|'.join(years)}"
            
        errors = self.validate_query(query)
        note = "✅ 年份已自动展开为逐年枚举格式（如 Y=2019|2020|...）。"
        if errors:
            note = "❌ 语法校验异常：" + "，".join(errors) + "。"
            
        return {
            "query": query, 
            "note": note
        }

# 策略注册表
TRANSLATOR_STRATEGIES = {
    "CNKI (知网)": CNKITranslator(),
    "Web of Science": WoSTranslator(),
    "IEEE Xplore": IEEETranslator(),
    "超星发现": CXTranslator()
}

def translate_queries(groups, dbs, start_year, end_year):
    """
    核心转译引擎 (基于策略模式)
    :param groups: 列表的列表，例如 [ [A组词], [B组词], [C组词] ]
    :param dbs: 用户勾选的目标数据库列表
    :param start_year: 起始年份
    :param end_year: 结束年份
    :return: dict，键为数据库名，值为包含 query 和 note 的字典
    """
    results = {}
    valid_groups = [g for g in groups if g]
    if not valid_groups:
        return results

    for db_name in dbs:
        strategy = TRANSLATOR_STRATEGIES.get(db_name)
        if strategy:
            results[db_name] = strategy.translate(valid_groups, start_year, end_year)
            
    return results
