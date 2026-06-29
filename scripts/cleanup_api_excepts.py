"""
清理 src/api/api.py 中冗余的 try/except Exception 块 - 改进版 v2.

策略:
  - 找到每个 `try:` 顶层 (4 空格缩进的函数体内) + 整个 except Exception 块
  - 删除整个 try:...except:... 包装, 只保留 try 内层代码 (缩进减少 4 空格)
  - 保留 except <specific> (如 ValueError, IOError)

这个脚本是 idempotent 的 (多次执行不会进一步损坏文件).
"""
import re
import sys
from pathlib import Path

api_path = Path('src/api/api.py')

with api_path.open('r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
result_lines = []
i = 0
removed_count = 0

while i < len(lines):
    line = lines[i]
    stripped = line.strip()

    # 检测函数体顶层的 try: (4 空格缩进, 函数体顶层)
    if stripped == 'try:' and line.startswith('    try:') and not line.startswith('        try:'):
        # 找到这个 try 对应的所有 except 子句
        # 顶级 try 块: 从 try: 开始, 到最后一个 except 子句结束
        try_start = i
        # 找 except 子句们 (可能多个 except)
        # 我们用栈式匹配 - 找到所有匹配这个 try 的 except 子句
        body_lines = []  # try: body 内的行
        j = i + 1
        try_indent_count = len(line) - len(line.lstrip())

        # 读取 try body
        while j < len(lines):
            l = lines[j]
            if not l.strip():
                body_lines.append(l)
                j += 1
                continue
            l_indent = len(l) - len(l.lstrip())
            # 在 body 内 (缩进 >= try 缩进 + 1)
            if l_indent > try_indent_count:
                body_lines.append(l)
                j += 1
                continue
            # 缩进与 try 一致 -> 这是 except 子句
            break

        # 现在 j 指向第一个 except (或如果结束函数就是 blank/下一个函数)
        # 检查 except 列表
        excepts = []
        while j < len(lines):
            l = lines[j]
            l_strip = l.strip()
            l_indent = len(l) - len(l.lstrip())

            if not l_strip:
                # 跳过空白
                j += 1
                continue

            # 必须与 try 同缩进
            if l_indent != try_indent_count:
                break

            if l_strip.startswith('except '):
                # 收集这一段 except 子句 (包含其 body)
                except_start = j
                # except body 缩进 = try_indent + 1
                k = j + 1
                while k < len(lines):
                    lk = lines[k]
                    if not lk.strip():
                        k += 1
                        continue
                    k_indent = len(lk) - len(lk.lstrip())
                    if k_indent > try_indent_count:
                        k += 1
                        continue
                    break

                # 收集 except 子句
                except_clause = '\n'.join(lines[except_start:k])
                excepts.append({
                    'start': except_start,
                    'end': k,
                    'line': lines[except_start],
                    'text': except_clause,
                    'specific': not l_strip.startswith('except Exception')
                })
                j = k
                continue

            break

        if not excepts:
            # 没找到任何 except - 不应发生, 跳过
            result_lines.append(line)
            i += 1
            continue

        # 判断: 是不是有 except Exception? (可以被兜底替代)
        has_generic_except = any(not e['specific'] for e in excepts)
        has_specific_only = all(e['specific'] for e in excepts)

        if has_generic_except:
            # 删除 except Exception 块, 保留 try body (缩进减少 4 空格)
            # 处理:
            #   1. 找出 except Exception 子句
            #   2. 其他 except (如有) 保留, 但要把它们的 body 缩进调整 (因为 try 没了)
            # 简化: 当且仅当 excepts 都是 except Exception 时, 完全展开 try
            if has_specific_only or len(excepts) > 1:
                # 混合: 保留 specific, 删 except Exception
                # 这个情况我们需要保留 except 子句, 但要去掉 except Exception
                # 复杂, 先不做 -- 仅处理最简单的纯 except Exception
                result_lines.append(line)
                i += 1
                continue

            # 全部 except 都是 except Exception -> 完全展开 try 块
            # 1) 跳过 try: 行本身
            # 2) 输出 body_lines (去除 4 空格缩进)
            for bl in body_lines:
                if bl.strip():
                    # 减少 4 空格缩进
                    if bl.startswith('    '):
                        result_lines.append(bl[4:])
                    else:
                        result_lines.append(bl)
                else:
                    result_lines.append(bl)

            # 跳过 except 子句们
            i = excepts[-1]['end']
            removed_count += 1
            continue

        else:
            # 只有 specific except - 保留整体 try/except 结构
            result_lines.append(line)
            i += 1
            continue

    result_lines.append(line)
    i += 1

# 写回文件
with api_path.open('w', encoding='utf-8') as f:
    f.write('\n'.join(result_lines))

print(f'[OK] Removed {removed_count} redundant try/except blocks')
print(f'[OK] {api_path} updated')
