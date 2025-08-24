"""
待解决：四对波浪号包裹的代码块，在正则中末尾少匹配一个波浪号。。
但一般使用四对反引号包裹嵌套代码块，嵌套规则已满足，所以暂时忽略。
"""

import re

# 代码块匹配正则（同时匹配多行代码块和单行内联代码）
code_pattern = re.compile(
    r'(`{1}[^`]+?`|`{3}[^`]+?`{3}|~{3}[\s\S]+?~{3}|````[\s\S]+?````)'
)


def save_code_blocks(content):
    """
    提取所有代码块和内联代码，并用占位符替代
    """
    # 提取所有代码块和内联代码
    code_blocks = code_pattern.findall(content)
    
    # 用占位符替代代码块和内联代码
    content = code_pattern.sub('__CODE_BLOCK__', content)

    return content, code_blocks


def restore_code_blocks(content, code_blocks):
    """
    按顺序将占位符替换回代码块和内联代码
    """
    for code_block in code_blocks:
        content = content.replace('__CODE_BLOCK__', code_block, 1)
    return content


# 示例
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

content, code_blocks = save_code_blocks(content)
print("code_blocks:", code_blocks)
print("content:", content)

content = restore_code_blocks(content, code_blocks)
