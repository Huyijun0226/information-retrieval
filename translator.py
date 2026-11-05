def parse_input(text):
    """将多行文本解析为有效词汇列表"""
    return [line.strip() for line in text.split('\n') if line.strip()]

def translate_queries(groups, dbs, start_year, end_year):
    """
    核心转译引擎
    :param groups: 列表的列表，例如 [ [A组词], [B组词], [D组词] ]
    :param dbs: 用户勾选的目标数据库列表
    :param start_year: 起始年份
    :param end_year: 结束年份
    :return: dict，键为数据库名，值为包含 query 和 note 的字典
    """
    results = {}
    valid_groups = [g for g in groups if g]
    if not valid_groups:
        return results

    if "CNKI (知网)" in dbs:
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
        results["CNKI (知网)"] = {
            "query": query, 
            "note": "✅ CNKI已自动清理了输入中的 `*` 和 `?` 通配符以防止语法错误。短语使用了单引号包裹。"
        }

    if "Web of Science" in dbs:
        # WoS规则：TS=("w1" OR w2) AND TS=(w3) AND PY=2019-2026
        wos_groups = []
        for g in valid_groups:
            # 带有空格或连字符的英文短语加双引号
            cleaned = [f'"{w}"' if (' ' in w or '-' in w) and not w.startswith('"') else w for w in g]
            wos_groups.append("TS=(" + " OR ".join(cleaned) + ")")
        query = " AND ".join(wos_groups)
        if start_year and end_year: 
            query += f" AND PY={start_year}-{end_year}"
        results["Web of Science"] = {
            "query": query, 
            "note": "✅ 已为带有空格或连字符的英文短语自动添加双引号。"
        }

    if "IEEE Xplore" in dbs:
        # IEEE规则：("w1" OR w2) AND (w3) （年份在侧边栏筛选，不在式子中）
        ieee_groups = []
        for g in valid_groups:
            cleaned = [f'"{w}"' if (' ' in w or '-' in w) and not w.startswith('"') else w for w in g]
            ieee_groups.append("(" + " OR ".join(cleaned) + ")")
        query = " AND ".join(ieee_groups)
        results["IEEE Xplore"] = {
            "query": query, 
            "note": "⚠️ 注意：请在 IEEE 检索结果页使用侧边栏 Year Range 勾选年份，检索式内不支持直接写年份。"
        }

    if "超星发现" in dbs:
        # 超星规则：Su=("w1"|w2)*("w3"|w4) AND Y=2019|2020|...
        cx_groups = []
        for g in valid_groups:
            cleaned = [f'"{w}"' if (' ' in w or '-' in w) and not w.startswith('"') else w for w in g]
            cx_groups.append("(" + "|".join(cleaned) + ")")
        query = "Su=" + "*".join(cx_groups)
        if start_year and end_year:
            years = [str(y) for y in range(int(start_year), int(end_year) + 1)]
            query += f" AND Y={'|'.join(years)}"
        results["超星发现"] = {
            "query": query, 
            "note": "✅ 年份已自动展开为逐年枚举格式（如 Y=2019|2020|...）。"
        }

    return results
