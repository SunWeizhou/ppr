import re

with open('docs/superpowers/plans/2026-05-11-phase4-recommendation-engine.md', 'r') as f:
    text = f.read()

# We need to extract the 3 specific python files for Task 6
service_content = None
api_content = None
viewmodel_content = None

blocks = re.split(r'```python', text)[1:]
for block in blocks:
    content = block.split('```')[0].strip()
    if '"""Recommendation workspace service for Paper Agent."""' in content:
        service_content = content
    elif '"""Recommendations API routes."""' in content:
        api_content = content
    elif '"""Recommendations workspace viewmodel."""' in content:
        viewmodel_content = content

if service_content:
    with open('app/services/recommendation_workspace_service.py', 'w') as f:
        f.write(service_content)
if api_content:
    with open('app/routes/api/recommendations.py', 'w') as f:
        f.write(api_content)
if viewmodel_content:
    with open('app/viewmodels/recommendations_viewmodel.py', 'w') as f:
        f.write(viewmodel_content)

print("Task 6 extracted!")
