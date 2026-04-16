# arXiv 论文推荐系统 - 安装配置指南

## 快速开始
### 方式 1: 一键安装（推荐）
```batch
双击 one_click_setup.bat
```
自动完成： 安装依赖 → Web 配置界面 → 启动服务器
### 方式 2: 噩令行配置
```batch
python installer/cli_wizard.py
```
### 方式 3: 智能配置（有 Zotero）
```batch
python installer/cli_wizard.py --smart
```
自动分析您的 Zotero 库， 推荐研究方向

---
## 配置导入/导出
### 导出配置
```batch
python installer/cli_wizard.py --export my_config.json
```
分享给同事使用
### 导入配置
```batch
python installer/cli_wizard.py --import my_config.json
```
直接使用同事分享的配置
---
## 功能说明
| 功能 | 说明 |
|------|------|
| Web 配置界面 | 可视化选择研究方向 |
| 噩令行向导 | 交互式配置 |
| 智能推荐 | 基于 Zotero 自动分析 |
| 配置导入/导出 | 方便分享和备份 |
| 一键安装 | 全自动安装配置 |

---

## 稡块文件
```
installer/
├── __init__.py           # 模块入口
├── templates.py         # 研究领域模板（17个方向）
├── cli_wizard.py         # 命令行配置向导
├── web_setup.py          # Web 配置界面
├── zotero_extractor.py   # Zotero 智能提取
├── one_click_setup.bat   # 一键安装脚本
├── setup.bat             # 配置向导入口
├── start_server.bat      # 启动服务器
├── run_daily.bat         # 每日运行
└── package.bat           # 打包分发
```

---

## 使用流程
```
给对方
    │
    ▼
解压整个项目文件夹
    │
    ▼
双击 installer/one_click_setup.bat
    │
    ├── 自动安装依赖
    ├── 打开 Web 配置界面
    └── 等待配置完成
    │
    ▼
访问 http://localhost:5555
    │
    ▼
查看推荐论文！
```
