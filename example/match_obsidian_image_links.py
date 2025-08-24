import re

# 测试示例
test_text = """
1. Obsidian 支持的 Wiki 链接格式

- 当前文件内锚点链接：`[[#标题]]`     
- 当前文件内块标识符链接：`[[#^块标识符]]`
- 普通文件链接：`[[assets/file1.md]]`
- 支持文件带锚点：`[[assets/file2.md#标题]]`
- 支持文件带块标识符：`[[assets/file3.md#^块标识符]]`
- 支持文件带别名：`[[assets/file4.md|别名]]`
- 支持文件带锚点和别名：`[[assets/file5.md#标题|别名]]`
- 支持文件带块标识符和别名：`[[assets/file6.md#^块标识符|别名]]`
- 图片资源链接：`![[assets/image1.png]]`
- 支持图片带尺寸声明：`![[assets/image2.png | 400x300]]`
- 支持图片仅指定宽度：`![[assets/image3.png | 400]]`

2. 标准 Markdown 链接格式

- 当前文件内锚点链接：`[别名](#标题)`
- 普通文件链接：`[别名](assets/file7.md)`
- 支持文件带锚点：`[别名](assets/file8.md#标题)`
- 图片资源链接：`![描述](assets/image4.png)`
- 普通资源链接指向图片：`[描述](assets/image5.png)`
   
3. Obsidian Markdown 扩展

- 当前文件内锚点嵌入：`![别名](#标题)`
- 当前文件内块标识符嵌入`![别名](#^块标识符)`
- 当前文件内块标识符链接：`[别名](#^块标识符)`
- 支持文件带块标识符：`[别名](assets/file9.md#^块标识符)`
- 支持图片带尺寸声明：`![400x300](assets/image6.png)`
- 支持图片带描述和尺寸声明：`![描述 | 400x300](assets/image7.png)`
- 支持图片带描述和仅宽度声明：`![描述 | 400](assets/image8.png)`

4. Obsidian 特殊嵌入格式

- 当前文件内锚点嵌入：`![[#标题]]`
- 当前文件内块标识符嵌入：`![[#^块标识符]]`
- 嵌入文件内容：`![[assets/file10.md]]`
- 嵌入 PDF 页面指定页数：`![[assets/doc.pdf#page=3]]`

5. 补充：

- ![描述](http://example.com/image.png)
- ![描述](https://example.com/audio.mp3)
- ![描述|400x300](assets/image%20copy.jpg)
"""

IMAGE_EXT = ('png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp', 'svg')

# Wiki 链接正则（支持路径/标题/块/尺寸/别名，竖线前后可有空格）
wiki_link_regex = r"""
    (!?)                           # 1: 可选 "!"（embed）
    \[\[
        (?:([^\]\|\n#^]+?)\s*)?    # 2: 路径（可选，自动去掉尾空格）
        (?:\#(?:
            (?!\^)([^\]\|\n#^]+)   # 3: 标题（#xxx）
          | \^([^\]\|\n#]+)        # 4: 块标识符（#^xxx）
        ))?
        (?:\s*\|\s*(\d{1,4}(?:x\d{1,4})?))?   # 5: 尺寸（400 或 400x300）
        (?:\s*\|\s*([^\]\n|]+))?              # 6: 别名
    \]\]
"""

# Markdown 链接正则（支持路径/标题/块/尺寸，描述去掉尾空格）
markdown_link_regex = r"""
    (!)?                           # 1: 可选 "!"（embed）
    \[
        ([^\]\|\n]*?)\s*           # 2: 描述/别名（去尾空格）
        (?:\s*\|\s*
            (\d{1,4}(?:x\d{1,4})?) # 3: 尺寸（400 或 400x300）
        )?
    \]
    \(
        ([^()\n#^]+?)?             # 4: 路径（可选）
        (?:\#(?:
            (?!\^)([^()\n#^]+)     # 5: 标题（#xxx）
          | \^([^()\n#]+)          # 6: 块标识符（#^xxx）
        ))?
    \)
"""

wiki_link_pattern = re.compile(wiki_link_regex, re.VERBOSE)
markdown_link_pattern = re.compile(markdown_link_regex, re.VERBOSE)


def is_image(path: str) -> bool:
    """判断是否为图片链接"""
    return path.lower().endswith(IMAGE_EXT)


def parse_desc_size(raw_desc_or_size, size_group):
    """解析图片描述和尺寸"""
    if not size_group:
        if raw_desc_or_size and re.match(r'^\d{1,4}(?:x\d{1,4})?$', raw_desc_or_size):
            return None, raw_desc_or_size
        return raw_desc_or_size, None

    return raw_desc_or_size, size_group


def extract_wiki_links(text):
    """Obsidian Wiki 链接解析"""
    matches = []
    for match in wiki_link_pattern.finditer(text):
        # print("match.groups():", match.groups())
        path = match.group(2) or None
        isImage = path and is_image(match.group(2))
        if isImage:
            # print("image_path:", match.group(2))
            embed = bool(match.group(1)) 
            title = match.group(3)
            block_id = match.group(4)
            desc = match.group(6)
            size = match.group(5)

            matches.append({
                'type': 'wiki',
                'embed': embed,
                'path': path,
                'title': title,
                'block_id': block_id,
                'desc': desc,
                'size': size,
            })

    return matches


def extract_markdown_links(text):
    """Obsidian Markdown 链接解析"""
    matches = []
    isImage = False
    for match in markdown_link_pattern.finditer(text):
        # print("match.groups():", match.groups())
        path = match.group(4)
        isImage = path and is_image(match.group(4))
        if isImage:
            embed = bool(match.group(1))
            raw_desc_or_size = match.group(2)
            size_group = match.group(3)
            path = match.group(4)
            desc, size = parse_desc_size(raw_desc_or_size, size_group)
            title = match.group(5)
            block_id = match.group(6)

            matches.append({
                'type': 'markdown',
                'embed': embed,
                'path': path,
                'title': title,
                'block_id': block_id,
                'desc': desc,
                'size': size,
            })

    return matches


matches = extract_wiki_links(test_text)

# for match in matches:
#     print(match)

matches += extract_markdown_links(test_text)

for match in matches:
    print(match)
