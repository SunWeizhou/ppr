# encoding: utf-8
"""
Web 配置界面 - 可视化配置向导

提供直观的 Web 界面让用户配置研究方向。
"""

from flask import Blueprint, render_template_string, jsonify, request
import json
import os
from pathlib import Path

web_setup = Blueprint('web_setup', __name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_FILE = PROJECT_ROOT / 'user_profile.json'


@web_setup.route('/setup')
def setup_page():
    """配置向导页面"""
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>arXiv 推荐系统 - 首次配置</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh;
            color: #e0e0e0;
            padding: 20px;
        }
        .container { max-width: 1000px; margin: 0 auto; }
        .header { text-align: center; padding: 30px; margin-bottom: 30px; }
        .header h1 { font-size: 2.2em; background: linear-gradient(135deg, #00d4ff, #7c3aed); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .header p { color: #888; margin-top: 10px; }

        .step-indicator {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 30px;
        }
        .step-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: rgba(255,255,255,0.2);
            transition: all 0.3s;
        }
        .step-dot.active { background: #00d4ff; transform: scale(1.2); }
        .step-dot.completed { background: #10b981; }

        .card {
            background: rgba(255,255,255,0.03);
            border-radius: 16px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.08);
            margin-bottom: 20px;
        }

        .section-title {
            font-size: 1.2em;
            color: #fff;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .section-title .icon { font-size: 1.3em; }

        .field-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 15px;
        }

        .field-card {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 15px;
            cursor: pointer;
            transition: all 0.2s;
            border: 2px solid transparent;
        }
        .field-card:hover { background: rgba(255,255,255,0.08); }
        .field-card.selected { border-color: #00d4ff; background: rgba(0,212,255,0.1); }
        .field-card h3 { color: #fff; font-size: 1em; margin-bottom: 8px; }
        .field-card p { color: #888; font-size: 0.85em; }

        .subfield-list {
            margin-top: 15px;
            padding: 15px;
            background: rgba(0,0,0,0.2);
            border-radius: 10px;
            display: none;
        }
        .subfield-list.show { display: block; }

        .subfield-item {
            display: flex;
            align-items: center;
            padding: 8px 12px;
            margin: 5px 0;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            cursor: pointer;
        }
        .subfield-item:hover { background: rgba(255,255,255,0.1); }
        .subfield-item.selected { background: rgba(0,212,255,0.2); }
        .subfield-item input { margin-right: 10px; }
        .subfield-item label { color: #ddd; cursor: pointer; flex: 1; }

        .input-group { margin: 15px 0; }
        .input-group label { display: block; color: #888; margin-bottom: 8px; }
        .input-group input, .input-group textarea {
            width: 100%;
            padding: 12px;
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(255,255,255,0.05);
            color: #fff;
            font-size: 0.95em;
        }
        .input-group input:focus, .input-group textarea:focus {
                outline: none;
                border-color: #00d4ff;
        }

        .btn {
            padding: 12px 30px;
            border-radius: 10px;
            border: none;
            cursor: pointer;
            font-size: 1em;
            transition: all 0.2s;
            margin: 5px;
        }
        .btn-primary {
            background: linear-gradient(135deg, #00d4ff, #7c3aed);
            color: #fff;
        }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(0,212,255,0.3); }
        .btn-secondary {
            background: rgba(255,255,255,0.1);
            color: #ddd;
        }
        .btn-secondary:hover { background: rgba(255,255,255,0.2); }

        .actions { display: flex; justify-content: center; gap: 10px; margin-top: 30px; }

        .preview-section {
            background: rgba(0,212,255,0.05);
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
            display: none;
        }
        .preview-section.show { display: block; }
        .preview-section h3 { color: #00d4ff; margin-bottom: 15px; }

        .keyword-tag {
            display: inline-block;
            padding: 4px 12px;
            margin: 3px;
            border-radius: 15px;
            font-size: 0.85em;
        }
        .keyword-core { background: rgba(16,185,129,0.3); color: #10b981; }
        .keyword-demote { background: rgba(239,68,68,0.3); color: #ef4444; }
        .keyword-custom { background: rgba(124,58,237,0.3); color: #a78bfa; }

        .import-export {
            display: flex;
            gap: 10px;
            margin-top: 20px;
            justify-content: center;
        }

        .file-input {
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎓 arXiv 论文推荐系统</h1>
            <p>首次配置 - 选择您的研究方向， 开始获取个性化推荐</p>
        </div>

        <div class="step-indicator">
            <div class="step-dot active" id="step1"></div>
            <div class="step-dot" id="step2"></div>
            <div class="step-dot" id="step3"></div>
            <div class="step-dot" id="step4"></div>
        </div>

        <!-- 步骤 1: 选择研究领域 -->
        <div class="card" id="card1">
            <div class="section-title">
                <span class="icon">📚</span>
                选择研究领域（可多选）
            </div>
            <div class="field-grid" id="fieldGrid"></div>
        </div>

        <!-- 步骤 2: 子领域 -->
        <div class="card" id="card2" style="display:none;">
            <div class="section-title">
                <span class="icon">🔬</span>
                选择子领域
            </div>
            <div id="subfieldContainer"></div>
        </div>

        <!-- 步骤 3: 自定义关键词 -->
        <div class="card" id="card3" style="display:none;">
            <div class="section-title">
                <span class="icon">✏️</span>
                自定义关键词（可选）
            </div>
            <div class="input-group">
                <label>添加自定义关键词（用逗号分隔）</label>
                <input type="text" id="customKeywords" placeholder="例如: neural tangent kernel, grokking, double descent">
            </div>
            <div class="input-group">
                <label>不感兴趣的关键词（用逗号分隔）</label>
                <input type="text" id="dislikeKeywords" placeholder="例如: federated learning, image generation. benchmark">
            </div>
        </div>

        <!-- 步骤 4: 偏好设置 -->
        <div class="card" id="card4" style="display:none;">
            <div class="section-title">
                <span class="icon">⚙️</span>
                偏好设置
            </div>
            <div class="input-group">
                <label>每日推荐论文数量</label>
                <input type="number" id="papersPerDay" value="20" min="5" max="50">
            </div>
            <div class="input-group">
                <label>
                    <input type="checkbox" id="preferTheory" checked>
                    偏好理论性论文
                </label>
            </div>

            <!-- 预览 -->
            <div class="preview-section" id="previewSection">
                <h3>📊 配置预览</h3>
                <div id="keywordPreview"></div>
            </div>

            <!-- 导入导出 -->
            <div class="import-export">
                <input type="file" id="importFile" class="file-input" accept=".json">
                <button class="btn btn-secondary" onclick="document.getElementById('importFile').click()">
                    📥 导入配置
                </button>
                <button class="btn btn-secondary" onclick="exportConfig()">
                    📤 导出配置
                </button>
            </div>
        </div>

        <div class="actions">
            <button class="btn btn-secondary" id="prevBtn" style="display:none;" onclick="prevStep()">
                ← 上一步
            </button>
            <button class="btn btn-primary" id="nextBtn" onclick="nextStep()">
                下一步 →
            </button>
            <button class="btn btn-primary" id="saveBtn" style="display:none;" onclick="saveConfig()">
                💾 保存配置
            </button>
        </div>
    </div>

    <script>
        // 研究领域数据
        const researchFields = {
            statistics: {
                name: '统计学',
                icon: '📊',
                fields: {
                    statistical_learning_theory: { name: '统计学习理论', subfields: ['泛化界', 'Minimax理论', 'PAC-Bayes', '集中不等式'] },
                    conformal_prediction: { name: 'Conformal Prediction', subfields: ['Split Conformal', 'Full Conformal', '自适应方法'] },
                    high_dimensional: { name: '高维统计', subfields: ['稀疏估计', '压缩感知', '随机矩阵'] },
                    bayesian: { name: '贝叶斯推断', subfields: ['MCMC', '变分推断', '贝叶斯优化'] },
                    causal: { name: '因果推断', subfields: ['处理效应', '因果发现', '工具变量'] }
                }
            },
            ml_theory: {
                name: '机器学习理论',
                icon: '🤖',
                fields: {
                    deep_learning_theory: { name: '深度学习理论', subfields: ['泛化', 'Double Descent', '隐式正则化', 'NTK'] },
                    llm_theory: { name: '大模型/LLM理论', subfields: ['In-Context Learning', 'Scaling Laws', '涌现能力', '对齐理论'] },
                    transformer_theory: { name: 'Transformer理论', subfields: ['注意力理论', '表达能力', '长度泛化'] },
                    optimization: { name: '优化理论', subfields: ['随机优化', '凸优化', '非凸优化', '加速方法'] },
                    rl_theory: { name: '强化学习理论', subfields: ['样本复杂度', '探索理论', '离线RL'] }
                }
            },
            cross: {
                name: '交叉领域',
                icon: '🔗',
                fields: {
                    uncertainty: { name: '不确定性量化', subfields: ['Conformal', '贝叶斯不确定性', '校准'] },
                    privacy: { name: '隐私保护学习', subfields: ['差分隐私', '联邦学习理论'] }
                }
            }
        };

        let currentStep = 1;
        let selectedFields = {};
        let selectedSubfields = {};

        // 初始化研究领域
        function initFields() {
            const grid = document.getElementById('fieldGrid');
            grid.innerHTML = '';

            for (const [catKey, category] of Object.entries(researchFields)) {
                for (const [fieldKey, field] of Object.entries(category.fields)) {
                    const card = document.createElement('div');
                    card.className = 'field-card';
                    card.innerHTML = `
                        <h3>${category.icon} ${field.name}</h3>
                        <p>${field.subfields.slice(0,3).join(', ')}...</p>
                    `;
                    card.onclick = () => toggleField(card, fieldKey, field, catKey);
                    grid.appendChild(card);
                }
            }
        }

        function toggleField(card, fieldKey, field, catKey) {
            card.classList.toggle('selected');

            if (selectedFields[fieldKey]) {
                delete selectedFields[fieldKey];
            } else {
                selectedFields[fieldKey] = { ...field, category: catKey };
            }

            updatePreview();
        }

        function nextStep() {
            if (currentStep === 1 && Object.keys(selectedFields).length === 0) {
                alert('请至少选择一个研究领域');
                return;
            }

            if (currentStep === 2) {
                // 收集选中的子领域
                document.querySelectorAll('.subfield-item.selected').forEach(item => {
                    const field = item.dataset.field;
                    const subfield = item.dataset.subfield;
                    if (!selectedSubfields[field]) selectedSubfields[field] = [];
                    selectedSubfields[field].push(subfield);
                });
            }

            currentStep++;
            updateUI();
        }

        function prevStep() {
            currentStep--;
            updateUI();
        }

        function updateUI() {
            // 更新步骤指示器
            document.querySelectorAll('.step-dot').forEach((dot, i) => {
                dot.classList.remove('active', 'completed');
                if (i + 1 < currentStep) dot.classList.add('completed');
                else if (i + 1 === currentStep) dot.classList.add('active');
            });

            // 显示/隐藏卡片
            for (let i = 1; i <= 4; i++) {
                document.getElementById('card' + i).style.display = i === currentStep ? 'block' : 'none';
            }

            // 更新按钮
            document.getElementById('prevBtn').style.display = currentStep > 1 ? 'block' : 'none';
            document.getElementById('nextBtn').style.display = currentStep < 4 ? 'block' : 'none';
            document.getElementById('saveBtn').style.display = currentStep === 4 ? 'block' : 'none';

            // 步骤2: 显示子领域
            if (currentStep === 2) {
                showSubfields();
            }

            // 步骤4: 显示预览
            if (currentStep === 4) {
                document.getElementById('previewSection').classList.add('show');
                updatePreview();
            }
        }

        function showSubfields() {
            const container = document.getElementById('subfieldContainer');
            container.innerHTML = '';

            for (const [fieldKey, field] of Object.entries(selectedFields)) {
                const section = document.createElement('div');
                section.innerHTML = `<h4 style="color:#888;margin:15px 0 5px;">${field.name}</h4>`;

                field.subfields.forEach(sf => {
                    const item = document.createElement('div');
                    item.className = 'subfield-item';
                    item.dataset.field = fieldKey;
                    item.dataset.subfield = sf;
                    item.innerHTML = `<label><input type="checkbox">${sf}</label>`;
                    item.onclick = (e) => {
                        if (e.target.tagName !== 'INPUT') {
                            item.classList.toggle('selected');
                            item.querySelector('input').checked = item.classList.contains('selected');
                        }
                    };
                    section.appendChild(item);
                });

                container.appendChild(section);
            }
        }

        function updatePreview() {
            const preview = document.getElementById('keywordPreview');
            let html = '';

            // 核心关键词
            const coreKeywords = [];
            Object.keys(selectedFields).forEach(f => {
                coreKeywords.push(f.replace(/_/g, ' '));
                if (selectedSubfields[f]) {
                    coreKeywords.push(...selectedSubfields[f]);
                }
            });

            if (coreKeywords.length > 0) {
                html += '<div style="margin-bottom:10px;color:#888;">核心关键词:</div>';
                coreKeywords.forEach(k => {
                    html += `<span class="keyword-tag keyword-core">${k}</span>`;
                });
            }

            // 自定义关键词
            const custom = document.getElementById('customKeywords').value;
            if (custom.trim()) {
                html += '<div style="margin:15px 0 10px;color:#888;">自定义:</div>';
                custom.split(',').forEach(k => {
                    if (k.trim()) html += `<span class="keyword-tag keyword-custom">${k.trim()}</span>`;
                });
            }

            // 不感兴趣
            const dislike = document.getElementById('dislikeKeywords').value;
            if (dislike.trim()) {
                html += '<div style="margin:15px 0 10px;color:#888;">不感兴趣:</div>';
                dislike.split(',').forEach(k => {
                    if (k.trim()) html += `<span class="keyword-tag keyword-demote">${k.trim()}</span>`;
                });
            }

            preview.innerHTML = html;
        }

        function saveConfig() {
            const config = {
                version: 2,
                keywords: {},
                theory_keywords: ['theorem', 'proof', 'bound', 'convergence', 'statistical'],
                settings: {
                    papers_per_day: parseInt(document.getElementById('papersPerDay').value),
                    prefer_theory: document.getElementById('preferTheory').checked
                },
                sources: {
                    arxiv_enabled: true,
                    journal_enabled: true
                }
            };

            // 添加关键词
            Object.keys(selectedFields).forEach(f => {
                config.keywords[f.replace(/_/g, ' ')] = { weight: 4.5, category: 'core' };
            });

            // 自定义关键词
            const custom = document.getElementById('customKeywords').value;
            if (custom.trim()) {
                custom.split(',').forEach(k => {
                    if (k.trim()) {
                        config.keywords[k.trim()] = { weight: 4.0, category: 'core' };
                    }
                });
            }

            // 不感兴趣
            const dislike = document.getElementById('dislikeKeywords').value;
            if (dislike.trim()) {
                dislike.split(',').forEach(k => {
                    if (k.trim()) {
                    config.keywords[k.trim()] = { weight: -1.5, category: 'dislike' };
                    }
                });
            }

            fetch('/setup/api/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            }).then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('✅ 配置已保存！ 即将跳转到首页...');
                    setTimeout(() => window.location.href = '/', 3000);
                } else {
                    alert('保存失败: ' + data.error);
                }
            });
        }

        function exportConfig() {
            const config = {
                selectedFields: selectedFields,
                selectedSubfields: selectedSubfields,
                customKeywords: document.getElementById('customKeywords').value,
                dislikeKeywords: document.getElementById('dislikeKeywords').value,
                papersPerDay: document.getElementById('papersPerDay').value,
                preferTheory: document.getElementById('preferTheory').checked
            };

            const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'my_config.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        document.getElementById('importFile').addEventListener('change', function(e) {
            const file = e.target.files[0];
            const reader = new FileReader();
            reader.onload = function(e) {
                try {
                    const config = JSON.parse(e.target.result);

                    // 应用导入的配置
                    selectedFields = config.selectedFields || {};
                    selectedSubfields = config.selectedSubfields || {};
                    document.getElementById('customKeywords').value = config.customKeywords || '';
                    document.getElementById('dislikeKeywords').value = config.dislikeKeywords || '';
                    document.getElementById('papersPerDay').value = config.papersPerDay;
                    document.getElementById('preferTheory').checked = config.preferTheory;

                    alert('✅ 配置已导入！');
                    updatePreview();
                } catch (err) {
                    alert('导入失败: ' + err);
                }
            };
        });

        // 初始化
        initFields();
    </script>
</body>
</html>
''')

@web_setup.route('/setup/api/save', methods=['POST'])
def save_config():
    """保存配置"""
    try:
        data = request.get_json()

        # 保存到 user_profile.json
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return jsonify({'success': True, 'message': '配置已保存'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


