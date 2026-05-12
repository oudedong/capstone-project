import re
from typing import Callable

from bs4 import BeautifulSoup, Comment


def replace_content_first(content: str, replace_content: str, tag: str) -> str:
    """content에서 처음으로 찾은 tag 요소를 replace_content로 교체합니다."""
    soup = BeautifulSoup(content, 'html.parser')
    target_tag = soup.find(tag)
    if target_tag is None:
        raise Exception("일치하는 요소가 없습니다")

    new_container = soup.new_tag("div", attrs={"class": "merged-iframe"})
    new_container.append(BeautifulSoup(replace_content, 'html.parser'))
    target_tag.replace_with(new_container)
    return str(soup)


async def recursive_iframe_replace(root) -> str:
    """재귀적으로 iframe 요소를 찾아 실제 내용으로 치환합니다."""
    child_iframes = root.child_frames
    content = await root.content()

    for iframe in child_iframes:
        if iframe.is_detached():  # 이미 분리된 프레임은 스킵
            continue
        content = replace_content_first(
            content,
            await recursive_iframe_replace(iframe),
            'iframe'
        )
    return content


def _remove_tags(html_content: str) -> str:
    """불필요한 태그와 속성을 제거합니다."""
    soup = BeautifulSoup(html_content, 'html.parser')

    # 주석 제거
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # 불필요한 태그 제거
    unwanted_tags = [
        'script', 'style', 'meta', 'link', 'noscript',
        'header', 'footer', 'svg',
        'input', 'button', 'form', 'select', 'textarea'
    ]
    for tag in soup.find_all(unwanted_tags):
        tag.decompose()

    # 중첩된 head 태그 제거
    for head in soup.find_all('head'):
        head.decompose()

    # 허용된 속성(href)만 남기고 나머지 제거
    allowed_attrs = ['href']
    for tag in soup.find_all(True):
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in allowed_attrs}

    if soup.body:
        return soup.body.decode_contents().strip()
    return str(soup).strip()


def _remove_empty_tags(html_content: str) -> str:
    """텍스트 내용이 없는 빈 태그들을 반복적으로 제거합니다."""
    soup = BeautifulSoup(html_content, 'html.parser')
    while True:
        removed = False
        for tag in soup.find_all():
            if not tag.get_text(strip=True) and not tag.find_all():
                tag.decompose()
                removed = True
        if not removed:
            break
    return str(soup).strip()


def _remove_gap(html_content: str) -> str:
    """탭, 연속 공백, 과도한 줄바꿈 등을 정리합니다."""
    html_content = re.sub(r'[\t\r]', ' ', html_content)
    html_content = re.sub(r' +', ' ', html_content)
    html_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', html_content)
    lines = [line.strip() for line in html_content.split('\n')]
    return '\n'.join(line for line in lines if line).strip()


def _apply_cleaners(html_content: str, cleaners: list[Callable[[str], str]]) -> str:
    """여러 후처리 함수를 순서대로 적용합니다."""
    for cleaner in cleaners:
        html_content = cleaner(html_content)
    return html_content


def clean_html(html_content: str) -> str:
    """불필요한 태그 제거 → 빈 태그 제거 → 공백 정리 순으로 후처리합니다."""
    return _apply_cleaners(html_content, [_remove_tags, _remove_empty_tags, _remove_gap])
