import os
import re

template_dir = 'templates'
classes_used = set()

# Regex to extract class="..." and class='...' (excluding :class or x-bind:class)
class_re = re.compile(r'(?<![:@\w])class=["\']([^"\']+)["\']')

custom_known_classes = {
    'custom-select-wrapper', 'custom-select-trigger', 'custom-select-menu', 'custom-select-option',
    'custom-select-label', 'custom-date-wrapper', 'custom-date-trigger', 'custom-date-popup',
    'custom-date-label', 'custom-scrollbar', 'safe-bottom', 'no-scrollbar', 'table-responsive',
    'tabular-nums', 'htmx-indicator', 'htmx-request', 'toast-item',
    # Spacing tokens (Fase 7I)
    'spacing-navbar-to-content', 'spacing-sections', 'spacing-title-to-content',
    'spacing-breadcrumb', 'spacing-before-footer', 'spacing-hero',
    # Django admin standard classes
    'action-counter', 'actions', 'breadcrumbs', 'button', 'clear', 'collapsed', 'default',
    'paginator', 'paginator-pages', 'question', 'rating', 'unread', 'showall', 'all',
    'admin-sidebar', 'admin-desktop-toggle', 'admin-mobile-toggle', 'admin-date-chip',
}

# Variable or JS syntax indicators
js_syntax_chars = set('{}$%?=<>&|!()[]{}+*^~')

for root, dirs, files in os.walk(template_dir):
    for f in files:
        if f.endswith('.html'):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8') as fp:
                content = fp.read()
                # Strip Django template tags and variables inside content
                clean_content = re.sub(r'\{%.*?%\}', ' ', content, flags=re.DOTALL)
                clean_content = re.sub(r'\{\{.*?\}\}', ' ', clean_content, flags=re.DOTALL)
                matches = class_re.findall(clean_content)
                for m in matches:
                    for c in m.split():
                        c = c.strip('",\'();')
                        if not c:
                            continue
                        if any(ch in c for ch in js_syntax_chars):
                            continue
                        # Skip template dot notation unless it's a numeric Tailwind value (e.g. gap-1.5)
                        if '.' in c and not re.match(r'^[a-z0-9\-:]+-[0-9]+\.[0-9]+', c):
                            continue
                        if c in custom_known_classes:
                            continue
                        if c.isdigit():
                            continue
                        classes_used.add(c)


with open('static/css/styles.css', 'r', encoding='utf-8') as fp:
    css_content = fp.read()

missing = []
for c in sorted(classes_used):
    # CSS selector escaping for Tailwind classes:
    # colons -> \:, brackets -> \[, slashes -> \/, dots -> \., percent -> \%, # -> \#, () -> \(\)
    escaped = re.sub(r'([:\[\]/\.%\#\(\)])', r'\\\1', c)
    target_selector = '.' + escaped
    if target_selector not in css_content and ('.' + c) not in css_content:
        missing.append(c)

print(f"Total unique classes scanned: {len(classes_used)}")
print(f"Total missing classes: {len(missing)}")
if missing:
    print("Missing classes:")
    for m in missing:
        print(f"  - {m}")
else:
    print("All template utility classes exist in static/css/styles.css!")

