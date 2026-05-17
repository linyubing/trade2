#!/usr/bin/env python3
"""修复 trading_agent.py 的 call_llm 方法：
   1. 处理 markdown 代码块包裹的 JSON
   2. 处理 deepseek-r1 的 reasoning_content
"""
import re

with open('agent/trading_agent.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到需要插入的位置: "content = message.content or \"\"" 之后的空行
insert_idx = None
for i, line in enumerate(lines):
    if 'content = message.content or' in line:
        # 找到后面第一个空行，在这里插入
        for j in range(i+1, min(i+5, len(lines))):
            if lines[j].strip() == '':
                insert_idx = j
                break
        break

if insert_idx is None:
    print("ERROR: 找不到插入位置!")
    exit(1)

fix = [
    '\n',
    '                # Handle deepseek-r1 thinking_content\n',
    '                if hasattr(message, "reasoning_content") and message.reasoning_content:\n',
    '                    logger.debug(f"LLM thinking: {message.reasoning_content[:200]}")\n',
    '\n',
    '                # Strip markdown code blocks before parsing JSON\n',
    '                import re\n',
    '                _json_match = re.search(r"```(?:json)?\\s*(\\{.*?\\})\\s*```", content, re.DOTALL)\n',
    '                if _json_match:\n',
    '                    content = _json_match.group(1).strip()\n',
    '                    logger.debug("Extracted JSON from markdown code block")\n',
    '\n',
]

print(f"在行 {insert_idx+1} 插入 {len(fix)} 行修复代码...")

new_lines = lines[:insert_idx] + fix + lines[insert_idx:]

with open('agent/trading_agent.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"完成! 新总行数: {len(new_lines)}")

# 验证语法
import py_compile
try:
    py_compile.compile('agent/trading_agent.py', doraise=True)
    print("✅ 语法检查通过!")
except py_compile.PyCompileError as e:
    print(f"❌ 语法错误: {e}")
    exit(1)
