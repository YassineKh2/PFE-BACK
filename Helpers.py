def extract_text_from_rich_content(data: dict) -> str:
    """
    Recursively extracts plain text from a Tiptap-style rich text JSON document.
    """
    texts = []

    def traverse(node):
        if isinstance(node, dict):
            if 'text' in node:
                texts.append(node['text'])
            if 'content' in node:
                for child in node['content']:
                    traverse(child)
        elif isinstance(node, list):
            for item in node:
                traverse(item)

    traverse(data)
    return ' '.join(texts).strip()
