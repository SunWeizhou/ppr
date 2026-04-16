"""
命令行配置向导

交互式引导用户完成系统配置。
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from .templates import (
    RESEARCH_TEMPLATES,
    get_fields_by_category,
    generate_config_from_selections
)


class SetupWizard:
    """配置向导类"""

    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(__file__).parent.parent
        self.config_file = self.base_dir / "user_profile.json"
        self.selected_fields: Dict[str, List[str]] = {}
        self.custom_keywords: Dict[str, float] = {}
        self.dislike_keywords: List[str] = []
        self.zotero_path: Optional[str] = None
        self.prefer_theory: bool = True

    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header(self, title: str):
        """打印标题头"""
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60)

    def print_step(self, step: int, total: int, title: str):
        """打印步骤标题"""
        print(f"\n[{step}/{total}] {title}")
        print("-" * 40)

    def ask_yes_no(self, prompt: str, default: bool = True) -> bool:
        """询问是/否问题"""
        default_str = "Y/n" if default else "y/N"
        while True:
            response = input(f"{prompt} [{default_str}]: ").strip().lower()
            if not response:
                return default
            if response in ('y', 'yes', '是'):
                return True
            if response in ('n', 'no', '否'):
                return False
            print("  请输入 y 或 n")

    def ask_choice(self, prompt: str, choices: List[str], allow_multi: bool = False) -> List[int]:
        """询问选择问题"""
        while True:
            response = input(prompt).strip()
            if not response:
                return []

            try:
                if allow_multi:
                    indices = [int(x.strip()) for x in response.split(',')]
                else:
                    indices = [int(response.strip())]

                if all(1 <= i <= len(choices) or i == 0 for i in indices):
                    return indices
                print(f"  请输入 0-{len(choices)} 之间的数字")
            except ValueError:
                print("  请输入有效的数字")

    def detect_zotero(self) -> Optional[str]:
        """检测 Zotero 数据库路径"""
        possible_paths = []

        if os.name == 'nt':  # Windows
            appdata = os.environ.get('APPDATA', '')
            local_appdata = os.environ.get('LOCALAPPDATA', '')
            possible_paths = [
                os.path.join(appdata, "Zotero", "Zotero", "zotero.sqlite"),
                os.path.join(local_appdata, "Zotero", "Zotero", "zotero.sqlite"),
                os.path.expanduser("~/Zotero/zotero.sqlite"),
                os.path.expanduser("~/Documents/Zotero/zotero.sqlite"),
            ]
        elif sys.platform == 'darwin':  # macOS
            possible_paths = [
                os.path.expanduser("~/Zotero/zotero.sqlite"),
                os.path.expanduser("~/Library/Application Support/Zotero/zotero.sqlite"),
            ]
        else:  # Linux
            possible_paths = [
                os.path.expanduser("~/Zotero/zotero.sqlite"),
                os.path.expanduser("~/.zotero/zotero.sqlite"),
            ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        return None

    def run(self):
        """运行配置向导"""
        self.clear_screen()

        print("\n")
        print("╔" + "═" * 58 + "╗")
        print("║" + " " * 10 + "arXiv 论文推荐系统 - 配置向导" + " " * 16 + "║")
        print("║" + " " * 58 + "║")
        print("║" + "  为统计学和机器学习研究者设计".center(48) + " " * 10 + "║")
        print("╚" + "═" * 58 + "╝")

        # 检查是否已有配置
        if self.config_file.exists():
            print(f"\n  检测到已有配置文件: {self.config_file}")
            if not self.ask_yes_no("  是否重新配置？", default=False):
                print("\n  保持现有配置，退出向导。")
                return

        # ========== 第一步：检测 Zotero ==========
        self.print_step(1, 5, "检测 Zotero")

        zotero_path = self.detect_zotero()
        if zotero_path:
            print(f"  ✓ 检测到 Zotero 数据库: {zotero_path}")
            if self.ask_yes_no("  是否使用 Zotero 进行智能配置分析？"):
                self.zotero_path = zotero_path
                # TODO: 调用 ZoteroExtractor 进行智能分析
                print("  (智能分析功能开发中...)")
        else:
            print("  未检测到 Zotero 数据库")
            print("  您可以稍后在设置中手动配置")

        # ========== 第二步：选择研究领域 ==========
        self.print_step(2, 5, "选择研究领域")

        categories = get_fields_by_category()
        field_list = []
        field_index = 1

        print("\n  请选择您的主要研究领域（可多选，用逗号分隔）:\n")

        for cat_name, fields in categories.items():
            print(f"  {cat_name}:")
            for key, data in fields.items():
                print(f"    {field_index}. {data['name']}")
                field_list.append((key, data))
                field_index += 1
            print()

        print(f"  0. 跳过（稍后手动配置）")

        choices = self.ask_choice("\n  请输入选项: ", [f[0] for f in field_list], allow_multi=True)

        if not choices or 0 in choices:
            print("\n  跳过领域选择，将使用默认配置。")
        else:
            # ========== 第三步：选择子领域 ==========
            self.print_step(3, 5, "选择研究子领域")

            for choice in choices:
                if choice == 0:
                    continue

                field_key, field_data = field_list[choice - 1]
                subfields = field_data.get("subfields", {})

                if not subfields:
                    continue

                print(f"\n  【{field_data['name']}】的子领域:")

                sf_list = list(subfields.items())
                for i, (sf_key, sf_data) in enumerate(sf_list, 1):
                    print(f"    {i}. {sf_data['name']}")

                print(f"\n    a. 全选    n. 全不选")

                sf_input = input("  请输入选项: ").strip().lower()

                if sf_input == 'a':
                    # 全选
                    self.selected_fields[field_key] = [sf_key for sf_key, _ in sf_list]
                    print(f"  ✓ 已选择全部 {len(sf_list)} 个子领域")
                elif sf_input == 'n':
                    continue
                else:
                    try:
                        sf_indices = [int(x.strip()) for x in sf_input.split(',')]
                        selected = [sf_list[i-1][0] for i in sf_indices if 1 <= i <= len(sf_list)]
                        if selected:
                            self.selected_fields[field_key] = selected
                            print(f"  ✓ 已选择 {len(selected)} 个子领域")
                    except ValueError:
                        print("  无效输入，跳过此领域")

        # ========== 第四步：自定义关键词 ==========
        self.print_step(4, 5, "自定义关键词")

        print("\n  您可以添加自定义的研究关键词")
        print("  格式: 关键词1:权重, 关键词2:权重")
        print("  示例: in-context learning:5.0, neural network:3.0")
        print("  (直接回车跳过)")

        custom_input = input("\n  自定义关键词: ").strip()
        if custom_input:
            try:
                for item in custom_input.split(','):
                    if ':' in item:
                        kw, weight = item.split(':')
                        self.custom_keywords[kw.strip()] = float(weight.strip())
                    else:
                        self.custom_keywords[item.strip()] = 4.0
                print(f"  ✓ 已添加 {len(self.custom_keywords)} 个自定义关键词")
            except ValueError:
                print("  格式错误，跳过自定义关键词")

        # 不感兴趣的关键词
        print("\n  是否有不感兴趣的研究方向？")
        print("  示例: federated learning, image generation, benchmark")
        print("  (直接回车跳过)")

        dislike_input = input("\n  不感兴趣的关键词: ").strip()
        if dislike_input:
            self.dislike_keywords = [kw.strip() for kw in dislike_input.split(',')]
            print(f"  ✓ 已添加 {len(self.dislike_keywords)} 个排除关键词")

        # ========== 第五步：偏好设置 ==========
        self.print_step(5, 5, "偏好设置")

        self.prefer_theory = self.ask_yes_no("\n  是否偏好理论性论文？", default=True)

        papers_per_day = input("  每日推荐论文数量 [20]: ").strip()
        papers_per_day = int(papers_per_day) if papers_per_day.isdigit() else 20

        # ========== 生成配置 ==========
        self.print_header("生成配置")

        config = generate_config_from_selections(
            self.selected_fields,
            self.custom_keywords,
            self.dislike_keywords
        )

        # 更新设置
        config["settings"]["prefer_theory"] = self.prefer_theory
        config["settings"]["papers_per_day"] = papers_per_day

        # 更新 Zotero 配置
        if self.zotero_path:
            config["zotero"]["database_path"] = self.zotero_path
            config["zotero"]["auto_detect"] = False

        # 统计信息
        total_keywords = len(config["keywords"])
        core_count = sum(1 for k in config["keywords"].values() if k["category"] == "core")

        print(f"\n  配置统计:")
        print(f"    - 研究领域: {len(self.selected_fields)} 个")
        print(f"    - 核心关键词: {core_count} 个")
        print(f"    - 总关键词: {total_keywords} 个")
        print(f"    - 排除关键词: {len(self.dislike_keywords)} 个")

        # 保存配置
        if self.ask_yes_no("\n  是否保存配置？", default=True):
            self.save_config(config)
            self.print_completion()
        else:
            print("\n  配置未保存，退出向导。")

    def save_config(self, config: Dict):
        """保存配置到文件"""
        try:
            # 备份现有配置
            if self.config_file.exists():
                backup_file = self.config_file.with_suffix('.json.bak')
                import shutil
                shutil.copy(self.config_file, backup_file)
                print(f"  ✓ 已备份现有配置到: {backup_file}")

            # 保存新配置
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            print(f"  ✓ 配置已保存到: {self.config_file}")
        except Exception as e:
            print(f"  ✗ 保存配置失败: {e}")

    def print_completion(self):
        """打印完成信息"""
        print("\n")
        print("╔" + "═" * 58 + "╗")
        print("║" + " " * 20 + "配置完成！" + " " * 26 + "║")
        print("╚" + "═" * 58 + "╝")

        print("\n  启动方式:")
        print("    1. 运行 Web 服务器:")
        print("       python web_server.py")
        print("\n    2. 访问 Web 界面:")
        print("       http://localhost:5555")
        print("\n    3. 获取推荐论文:")
        print("       python arxiv_recommender_v5.py")

        print("\n  您可以随时通过 Web 界面调整设置:")
        print("    http://localhost:5555/settings")

        print("\n" + "=" * 60)

    # ========== 新增: 配置导入导出 ==========

    def export_config(self, filepath: str = None) -> str:
        """导出当前配置到文件

        Args:
            filepath: 导出路径，默认为 'my_config.json'

        Returns:
            导出的文件路径
        """
        if not self.config_file.exists():
            print("  ✗ 没有可导出的配置， 请先完成配置")
            return None

        export_path = Path(filepath) if filepath else self.base_dir / "my_config.json"

        try:
            import shutil
            shutil.copy(self.config_file, export_path)
            print(f"  ✓ 配置已导出到: {export_path}")
            print(f"    可以分享给做类似研究的同事！")
            return str(export_path)
        except Exception as e:
            print(f"  ✗ 导出失败: {e}")
            return None

    def import_config(self, filepath: str) -> bool:
        """从文件导入配置

        Args:
            filepath: 要导入的配置文件路径

        Returns:
            是否成功
        """
        import_path = Path(filepath)

        if not import_path.exists():
            print(f"  ✗ 文件不存在: {filepath}")
            return False

        try:
            import shutil
            shutil.copy(import_path, self.config_file)
            print(f"  ✓ 配置已导入: {filepath}")
            print("    请重启服务使配置生效")
            return True
        except Exception as e:
            print(f"  ✗ 导入失败: {e}")
            return False

    def show_import_export_menu(self):
        """显示导入导出菜单"""
        print("\n  配置导入/导出:")
        print("  1. 导出当前配置")
        print("  2. 导入配置文件")
        print("  0. 返回")

        choice = input("\n  请选择: ").strip()

        if choice == '1':
            filename = input("  导出文件名 [my_config.json]: ").strip() or "my_config.json"
            self.export_config(filename)
        elif choice == '2':
            filepath = input("  配置文件路径: ").strip()
            if filepath:
                self.import_config(filepath)


        elif choice == '0':
            return

    # ========== 新增: 智能推荐配置 ==========

    def smart_recommend(self) -> Dict:
        """基于 Zotero 智能推荐配置

        Returns:
            推荐的配置
        """
        try:
            from .zotero_extractor import ZoteroExtractor

            print("\n  正在分析您的 Zotero 文献库...")
            extractor = ZoteroExtractor()
            extractor.load_papers(300)  # 分析最近300篇

            if not extractor.papers:
                print("  未找到 Zotero 论文，请手动配置")
                return None

            # 提取关键词和推荐
            result = extractor.get_recommended_config()

            print(f"\n  ✓ 分析了 {result['paper_count']} 篇论文")

            # 显示推荐结果
            print("\n  推荐的研究方向:")
            for full_key, score in list(result['matched_subfields'].items())[:5]:
                print(f"    - {full_key}: {score:.2f}")

            print("\n  提取的关键词:")
            for kw, score in list(result['extracted_keywords'].items())[:10]:
                print(f"    - {kw}: {score:.1f}")

            return result

        except Exception as e:
            print(f"  智能分析失败: {e}")
            return None


def run_setup():
    """运行配置向导的入口函数"""
    import argparse

    parser = argparse.ArgumentParser(description='arXiv 论文推荐系统配置向导')
    parser.add_argument('--smart', action='store_true', help='使用智能推荐（基于 Zotero）')
    parser.add_argument('--export', type=str, help='导出配置到文件')
    parser.add_argument('--import-config', dest='import_config', type=str, help='从文件导入配置')

    args = parser.parse_args()

    wizard = SetupWizard()

    # 处理命令行参数
    if args.export:
        wizard.export_config(args.export)
        return

    if args.import_config:
        wizard.import_config(args.import_config)
        return

    if args.smart:
        # 智能推荐模式
        result = wizard.smart_recommend()
        if result and wizard.ask_yes_no("\n是否使用推荐配置？"):
            # 应用推荐配置
            config = result['config']
            wizard.save_config(config)
            wizard.print_completion()
        return

    # 正常交互模式
    wizard.run()


if __name__ == "__main__":
    run_setup()
