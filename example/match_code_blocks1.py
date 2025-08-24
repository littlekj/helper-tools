import re


# 示例内容
content = """
这是一个示例文本，其中包含以下代码块：

```python
def hello_world():
    print("Hello, world!")
```

以及内联代码 `print("Hello, world!")`。

还有另一个代码块：

~~~python
def add(a, b):
    return a + b
~~~

以及内联代码 `add(1, 2)`。

还有嵌套代码块：

````
```query
嵌入 OR 搜索
```
````

四对反引号的代码块：

````python
def hello_world():
    print("Hello, world!")
````

四对波浪号的代码块：

~~~~python
def hello_world():
    print("Hello, world!")
~~~~

"""

# 匹配内联代码 和 多行代码块（反引号/波浪号，3个或以上）
# 改进的正则：为每种情况设置捕获组，并确保内容被捕获
CODE_PATTERN = re.compile(
    r'(`[^`]+?`)'                                  # group 1: 内联代码
    r'|(~{3,})([a-zA-Z][\w-]*)?\s*\n'              # group 2: 波浪号开始, group 3: 语言
    r'([\s\S]*?)\n'                                # group 4: 波浪号内容
    r'(~{3,})(?=\n|$)'                             # group 5: 波浪号结束
    r'|(`{3,})([a-zA-Z][\w-]*)?\s*\n'              # group 6: 反引号开始, group 7: 语言
    r'([\s\S]*?)\n'                                # group 8: 反引号内容
    r'(`{3,})(?=\n|$)',                            # group 9: 反引号结束
    re.MULTILINE
)


def save_code_blocks(content):
    code_blocks = []
    placeholder_counter = 0

    def replace_func(match):
        nonlocal placeholder_counter
        placeholder_counter += 1
        placeholder = f"__CODE_BLOCK_{placeholder_counter}__"

        if match.group(1):  # 内联代码
            code = match.group(1)
        elif match.group(2):  # 波浪号代码块
            start_delim = match.group(2)   # ~~~
            lang = match.group(3) or ""    # 可选语言
            body = match.group(4)
            end_delim = match.group(5)     # ~~~
            # 保留语言标识
            code = f"{start_delim}{lang}\n{body}\n{end_delim}"
        else:  # 反引号代码块
            start_delim = match.group(6)   # ```
            lang = match.group(7) or ""    # 可选语言
            body = match.group(8)
            end_delim = match.group(9)     # ```
            # 保留语言标识
            code = f"{start_delim}{lang}\n{body}\n{end_delim}"

        code_blocks.append((placeholder, code))
        return placeholder

    new_content = CODE_PATTERN.sub(replace_func, content)
    return new_content, code_blocks


def restore_code_blocks(content, code_blocks):
    """
    将占位符替换回原始代码块
    """
    for placeholder, code in code_blocks:
        content = content.replace(placeholder, code)
    return content


content, code_blocks = save_code_blocks(content)
print("code_blocks:", code_blocks)
print("content:", content)

content = restore_code_blocks(content, code_blocks)

print("content:", content)
