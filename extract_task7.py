import re

with open('docs/superpowers/plans/2026-05-11-phase4-recommendation-engine.md', 'r') as f:
    text = f.read()

# We need to extract the 2 specific files for Task 7
html_content = None
css_content = None

blocks = re.split(r'```', text)
for i in range(len(blocks)):
    if blocks[i].startswith('html') and '{% extends "base_research.html" %}' in blocks[i]:
        html_content = blocks[i][4:].strip()
    elif blocks[i].startswith('css') and 'Recommendation Page — Sectioned Card Layout' in blocks[i]:
        css_content = blocks[i][3:].strip()

if html_content:
    with open('templates/recommendations.html', 'w') as f:
        f.write(html_content)
if css_content:
    with open('static/research_ui.css', 'a') as f:
        f.write("\n" + css_content + "\n")

print("Task 7 extracted!")
