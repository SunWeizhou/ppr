"""Scholar database for curated researcher tracking.

This is pure reference data and contains no business logic.
"""

SCHOLARS = {
    'icl_transformer': {
        'name': 'ICL 与 Transformer 理论核心',
        'icon': '🤖',
        'color': '#00d4ff',
        'description': '解析 ICL 样本复杂度、隐式优化和贝叶斯推断的最前沿学者',
        'scholars': [
            {
                'name': 'Yue M. Lu',
                'affiliation': 'Harvard',
                'focus': 'ICL 统计力学视角',
                'description': '利用非线性统计物理工具分析线性注意力的渐进学习曲线',
                'google_scholar': 'https://scholar.google.com/citations?user=wc0FCZUAAAAJ',
                'website': 'https://yuelu-website.webflow.io/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Lu%2C+Yue+M'
            },
            {
                'name': 'Tengyu Ma',
                'affiliation': 'Stanford',
                'focus': '特征学习与复杂度',
                'description': '证明了 Transformer 在处理低秩结构任务时的统计收敛率',
                'google_scholar': 'https://scholar.google.com/citations?user=i38QlUwAAAAJ',
                'website': 'https://ai.stanford.edu/~tengyuma/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Ma%2C+Tengyu'
            },
            {
                'name': 'Song Mei',
                'affiliation': 'UC Berkeley',
                'focus': '平均场与风险演化',
                'description': '分析自回归模型在预训练与推理阶段的风险界限',
                'google_scholar': 'https://scholar.google.com/citations?user=MhDyxdYAAAAJ',
                'website': 'https://www.stat.berkeley.edu/~songmei/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Mei%2C+Song'
            },
            {
                'name': 'Jason D. Lee',
                'affiliation': 'Princeton',
                'focus': '隐式梯度下降',
                'description': '探讨 Transformer 前向传播作为优化算法的数学本质',
                'google_scholar': 'https://scholar.google.com/citations?user=GR_DsT0AAAAJ',
                'website': 'https://jasondlee.com/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Lee%2C+Jason+D'
            },
            {
                'name': 'Johannes von Oswald',
                'affiliation': 'ETH Zurich',
                'focus': '权重推断',
                'description': '提出了 Transformer 内部执行隐式梯度更新的奠基性观点',
                'google_scholar': 'https://scholar.google.com/citations?user=-K0FZcUAAAAJ',
                'website': 'https://mlcb.robots.ox.ac.uk/people/johannes-von-oswald/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Oswald%2C+Johannes+von'
            },
            {
                'name': 'Sanjeev Arora',
                'affiliation': 'Princeton',
                'focus': '表示学习与隐变量',
                'description': '研究预训练如何通过统计关联捕获上下文推断能力',
                'google_scholar': 'https://scholar.google.com/citations?user=RUP4S68AAAAJ',
                'website': 'https://www.cs.princeton.edu/~arora/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Arora%2C+Sanjeev'
            },
            {
                'name': 'Yihong Wu',
                'affiliation': 'Yale',
                'focus': '信息论界限',
                'description': '给出了 ICL 任务在最小二乘意义下的样本复杂度下界',
                'google_scholar': 'https://scholar.google.com/citations?user=HQRnt54AAAAJ',
                'website': 'https://stats.yale.edu/people/faculty/yihong-wu',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Wu%2C+Yihong'
            },
            {
                'name': 'Boaz Barak',
                'affiliation': 'Harvard',
                'focus': '相变与顿悟 (Grokking)',
                'description': '研究深度学习中从记忆到泛化的统计相变',
                'google_scholar': 'https://scholar.google.com/citations?user=I0fbJ6cAAAAJ',
                'website': 'https://boazbarak.org/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Barak%2C+Boaz'
            },
            {
                'name': 'Simon Du',
                'affiliation': 'Univ. of Washington',
                'focus': '过参数化分析',
                'description': '分析大规模 Transformer 在插值机制下的泛化表现',
                'google_scholar': 'https://scholar.google.com/citations?user=OttawxUAAAAJ',
                'website': 'https://simonshaoleidu.com/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Du%2C+Simon+S'
            },
            {
                'name': 'Christopher Ré',
                'affiliation': 'Stanford',
                'focus': '架构统计特性',
                'description': '对比线性循环结构（如 Mamba）与 Transformer 的 ICL 等价性',
                'google_scholar': 'https://scholar.google.com/citations?user=DnnCWN0AAAAJ',
                'website': 'https://cs.stanford.edu/people/chrismre/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=R%C3%A9%2C+Christopher'
            }
        ]
    },
    'generalization': {
        'name': '泛化理论与统计复杂性',
        'icon': '📐',
        'color': '#10b981',
        'description': '研究过参数化模型在"良性过拟合"状态下的稳定性与风险界限',
        'scholars': [
            {
                'name': 'Peter Bartlett',
                'affiliation': 'UC Berkeley',
                'focus': '良性过拟合、Rademacher 复杂度',
                'description': '核心人物，研究神经网络 Lipschitz 稳定性',
                'google_scholar': 'https://scholar.google.com/citations?user=yQNhFGUAAAAJ',
                'website': 'https://www.stat.berkeley.edu/~bartlett/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Bartlett%2C+Peter+L'
            },
            {
                'name': 'Mikhail Belkin',
                'affiliation': 'UCSD',
                'focus': '双下降理论',
                'description': '彻底改变了统计学对偏置-方差权衡的认知',
                'google_scholar': 'https://scholar.google.com/citations?user=Iwd9DdkAAAAJ',
                'website': 'https://mbelkin.ucsd.edu/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Belkin%2C+Mikhail'
            },
            {
                'name': 'Sasha Rakhlin',
                'affiliation': 'MIT',
                'focus': '在线学习与稳定性',
                'description': '发展了序列预测与非参数统计的统一证明框架',
                'google_scholar': 'https://scholar.google.com/citations?user=fds2VpgAAAAJ',
                'website': 'https://www.mit.edu/~rakhlin/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Rakhlin%2C+Alexander'
            },
            {
                'name': 'Matus Telgarsky',
                'affiliation': 'NYU',
                'focus': '深度学习边界',
                'description': '专注于神经网络在无穷深/宽限制下的复杂度分析',
                'google_scholar': 'https://scholar.google.com/citations?user=Fc-5yRIAAAAJ',
                'website': 'https://mjt.cs.illinois.edu/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Telgarsky%2C+Matus'
            },
            {
                'name': 'Francis Bach',
                'affiliation': 'INRIA/ENS',
                'focus': '核方法与非凸优化',
                'description': '从再生核希尔伯特空间视角审视深度学习稳定性',
                'google_scholar': 'https://scholar.google.com/citations?user=6PJWcFEAAAAJ',
                'website': 'https://www.di.ens.fr/~fbach/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Bach%2C+Francis'
            },
            {
                'name': 'Lenka Zdeborová',
                'affiliation': 'EPFL',
                'focus': '统计物理交叉',
                'description': '研究计算困难度与统计可学习性之间的相变',
                'google_scholar': 'https://scholar.google.com/citations?user=gkCjy_UAAAAJ',
                'website': 'https://ipht.cea.fr/en/personnel/zdeborova/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Zdeborov%C3%A1%2C+Lenka'
            },
            {
                'name': 'Vitaly Feldman',
                'affiliation': 'Apple/Google',
                'focus': '统计查询 (SQ) 模型',
                'description': '研究隐私保护下的学习界限',
                'google_scholar': 'https://scholar.google.com/citations?user=GqZBmfgAAAAJ',
                'website': 'https://vitaly.feldman.research/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Feldman%2C+Vitaly'
            },
            {
                'name': 'Sivan Sabato',
                'affiliation': 'Ben-Gurion Univ.',
                'focus': '主动学习理论',
                'description': '研究交互式数据获取的统计效率',
                'google_scholar': 'https://scholar.google.com/citations?user=4jTn-qIAAAAJ',
                'website': 'https://www.cs.bgu.ac.il/~sabatos/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Sabato%2C+Sivan'
            },
            {
                'name': 'Masaaki Imaizumi',
                'affiliation': 'Univ. of Tokyo',
                'focus': '非参数视角',
                'description': '从统计推断角度解析深度神经网络的层级结构',
                'google_scholar': 'https://scholar.google.com/citations?user=ZwDzTTwAAAAJ',
                'website': 'https://www.ms.u-tokyo.ac.jp/en/people/imaizumi.html',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Imaizumi%2C+Masaaki'
            },
            {
                'name': 'Gérard Ben Arous',
                'affiliation': 'NYU',
                'focus': '随机景观 (Landscapes)',
                'description': '研究非凸损失函数的拓扑复杂性',
                'google_scholar': 'https://scholar.google.com/citations?user=ZQhFI_EAAAAJ',
                'website': 'https://math.nyu.edu/people/profiles/BENAROUS_Gerard.html',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Ben+Arous%2C+G%C3%A9rard'
            }
        ]
    },
    'high_dim_stats': {
        'name': '高维统计与现代推断',
        'icon': '📊',
        'color': '#8b5cf6',
        'description': '为大规模模型提供严谨的统计工具，如符合预测、变量选择和鲁棒性',
        'scholars': [
            {
                'name': 'Emmanuel Candès',
                'affiliation': 'Stanford',
                'focus': '符合预测 (Conformal Prediction)',
                'description': '为 LLM 输出提供严谨的统计置信区间',
                'google_scholar': 'https://scholar.google.com/citations?user=BrLyrxEAAAAJ',
                'website': 'https://statistics.stanford.edu/people/emmanuel-candes',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Cand%C3%A8s%2C+Emmanuel+J'
            },
            {
                'name': 'Martin J. Wainwright',
                'affiliation': 'MIT',
                'focus': '高维统计圣经作者',
                'description': '非渐进统计分析与信息论界限',
                'google_scholar': 'https://scholar.google.com/citations?user=p1DZVX8AAAAJ',
                'website': 'https://www.stat.berkeley.edu/~wainwrig/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Wainwright%2C+Martin+J'
            },
            {
                'name': 'John Duchi',
                'affiliation': 'Stanford',
                'focus': '鲁棒性与隐私',
                'description': '优化与统计融合的领军人物',
                'google_scholar': 'https://scholar.google.com/citations?user=i5srt20AAAAJ',
                'website': 'https://web.stanford.edu/~jduchi/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Duchi%2C+John+C'
            },
            {
                'name': 'Rina Foygel Barber',
                'affiliation': 'UChicago',
                'focus': '虚假发现率 (FDR)',
                'description': '研究高维模型中的选择性推断',
                'google_scholar': 'https://scholar.google.com/citations?user=k5HsbdcAAAAJ',
                'website': 'https://stat.uchicago.edu/people/profile/rina-foygel-barber/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Barber%2C+Rina+Foygel'
            },
            {
                'name': 'Tony Cai (蔡天文)',
                'affiliation': 'Wharton',
                'focus': '适应性估计',
                'description': '高维推断与大规模数据测试的权威',
                'google_scholar': 'https://scholar.google.com/citations?user=v1MTZmIAAAAJ',
                'website': 'https://statistics.wharton.upenn.edu/profile/tcai/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Cai%2C+T+Tony'
            },
            {
                'name': 'Harrison Zhou (周)',
                'affiliation': 'Yale',
                'focus': '贝叶斯非参数',
                'description': '统计收敛率与后验分布的渐进性质',
                'google_scholar': 'https://scholar.google.com/citations?user=lTCxlGYAAAAJ',
                'website': 'https://statistics.yale.edu/people/harrison-zhou',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Zhou%2C+Harrison'
            },
            {
                'name': 'Jianqing Fan (范剑青)',
                'affiliation': 'Princeton',
                'focus': '变量选择',
                'description': '超高维数据分析与 SIS 筛选',
                'google_scholar': 'https://scholar.google.com/citations?user=TaF4L4EAAAAJ',
                'website': 'https://orfe.princeton.edu/people/jianqing-fan',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Fan%2C+Jianqing'
            },
            {
                'name': 'Robert Tibshirani',
                'affiliation': 'Stanford',
                'focus': 'LASSO 创始人',
                'description': '稀疏统计与收缩估计的代表',
                'google_scholar': 'https://scholar.google.com/citations?user=ZpG_cJwAAAAJ',
                'website': 'https://statistics.stanford.edu/people/robert-tibshirani',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Tibshirani%2C+Robert'
            },
            {
                'name': 'Trevor Hastie',
                'affiliation': 'Stanford',
                'focus': 'ESL 作者',
                'description': '定义了现代统计学习的教学架构',
                'google_scholar': 'https://scholar.google.com/citations?user=WSmKJqoAAAAJ',
                'website': 'https://statistics.stanford.edu/people/trevor-hastie',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Hastie%2C+Trevor'
            },
            {
                'name': 'Ryan Tibshirani',
                'affiliation': 'UC Berkeley',
                'focus': '凸优化与平滑',
                'description': '研究统计估计器的计算边界',
                'google_scholar': 'https://scholar.google.com/citations?user=cQ1P1qoAAAAJ',
                'website': 'https://www.stat.berkeley.edu/~ryantibs/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Tibshirani%2C+Ryan'
            }
        ]
    },
    'foundational_stats': {
        'name': '经典统计学、经验过程与稳定性',
        'icon': '📚',
        'color': '#f59e0b',
        'description': '研究统计推断的稳定性、一致性以及样本效率的根基',
        'scholars': [
            {
                'name': 'Larry Wasserman',
                'affiliation': 'CMU',
                'focus': '非参数推断',
                'description': '专注于不依赖分布假设的稳健推断',
                'google_scholar': 'https://scholar.google.com/citations?user=XcD1ffwAAAAJ',
                'website': 'https://www.stat.cmu.edu/~larry/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Wasserman%2C+Larry'
            },
            {
                'name': 'Bin Yu (郁彬)',
                'affiliation': 'UC Berkeley',
                'focus': 'PCS 框架',
                'description': '强调统计结论的可预测性与稳定性',
                'google_scholar': 'https://scholar.google.com/citations?user=KDDbvXsAAAAJ',
                'website': 'https://statistics.berkeley.edu/people/bin-yu',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Yu%2C+Bin'
            },
            {
                'name': 'Peter Bühlmann',
                'affiliation': 'ETH Zurich',
                'focus': '因果推断',
                'description': '研究高维环境下的干预效果与稳定性',
                'google_scholar': 'https://scholar.google.com/citations?user=3r-fWJwAAAAJ',
                'website': 'https://stat.ethz.ch/people/buhlmann',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=B%C3%BChlmann%2C+Peter'
            },
            {
                'name': 'Michael I. Jordan',
                'affiliation': 'UC Berkeley',
                'focus': '变分推断',
                'description': '统计与机器学习交叉领域的奠基人',
                'google_scholar': 'https://scholar.google.com/citations?user=yxUduqMAAAAJ',
                'website': 'https://people.eecs.berkeley.edu/~jordan/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Jordan%2C+Michael+I'
            },
            {
                'name': 'David Donoho',
                'affiliation': 'Stanford',
                'focus': '稀疏性与多尺度',
                'description': '高维统计计算的先驱',
                'google_scholar': 'https://scholar.google.com/citations?user=ubaxhUIAAAAJ',
                'website': 'https://statistics.stanford.edu/people/david-donoho',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Donoho%2C+David+L'
            },
            {
                'name': 'Aad van der Vaart',
                'affiliation': 'TU Delft',
                'focus': '经验过程',
                'description': '研究随机过程收敛性的核心数学理论',
                'google_scholar': 'https://scholar.google.com/citations?user=SkH-ZyIAAAAJ',
                'website': 'https://awstg.nl/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=van+der+Vaart%2C+Aad'
            },
            {
                'name': 'Sara van de Geer',
                'affiliation': 'ETH Zurich',
                'focus': 'L1 正则化',
                'description': '高维经验过程与稀疏性证明的权威',
                'google_scholar': 'https://scholar.google.com/citations?user=KNiO4pwAAAAJ',
                'website': 'https://stat.ethz.ch/people/vandegeer',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=van+de+Geer%2C+Sara'
            },
            {
                'name': 'Art B. Owen',
                'affiliation': 'Stanford',
                'focus': '经验似然',
                'description': '非参数统计中的重要工具',
                'google_scholar': 'https://scholar.google.com/citations?user=MowD-YYAAAAJ',
                'website': 'https://statistics.stanford.edu/people/art-owen',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Owen%2C+Art+B'
            },
            {
                'name': 'Subhashis Ghosal',
                'affiliation': 'NC State',
                'focus': '贝叶斯收敛',
                'description': '贝叶斯非参数统计的理论高度',
                'google_scholar': 'https://scholar.google.com/citations?user=u2tifuYAAAAJ',
                'website': 'https://stat.sciences.ncsu.edu/people/ghosal/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Ghosal%2C+Subhashis'
            },
            {
                'name': 'Enno Mammen',
                'affiliation': 'Heidelberg',
                'focus': '半参数模型',
                'description': '平滑技术与函数估计的数学理论',
                'google_scholar': 'https://scholar.google.com/citations?user=X6DfPHIAAAAJ',
                'website': 'https://www.mathi.uni-heidelberg.de/~mammen/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Mammen%2C+Enno'
            }
        ]
    },
    'probability_tools': {
        'name': '概率工具、鲁棒性与可靠性',
        'icon': '🎲',
        'color': '#ef4444',
        'description': '提供随机矩阵、集中不等式等"硬核"理论工具，并关注分布偏移',
        'scholars': [
            {
                'name': 'Roman Vershynin',
                'affiliation': 'UCI',
                'focus': '高维概率',
                'description': '其著作是推导泛化界限的必备手册',
                'google_scholar': 'https://scholar.google.com/citations?user=xXGM4gcAAAAJ',
                'website': 'https://www.math.uci.edu/~rvershyn/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Vershynin%2C+Roman'
            },
            {
                'name': 'Joel Tropp',
                'affiliation': 'Caltech',
                'focus': '随机矩阵',
                'description': '矩阵集中不等式及其在计算中的应用',
                'google_scholar': 'https://scholar.google.com/citations?user=i4_3daEAAAAJ',
                'website': 'https://tropp.caltech.edu/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Tropp%2C+Joel+A'
            },
            {
                'name': 'Aleksander Madry',
                'affiliation': 'MIT',
                'focus': '对抗鲁棒性',
                'description': '研究统计推断在极端干扰下的表现',
                'google_scholar': 'https://scholar.google.com/citations?user=SupjsEUAAAAJ',
                'website': 'https://people.csail.mit.edu/madry/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Madry%2C+Aleksander'
            },
            {
                'name': 'Jacob Steinhardt',
                'affiliation': 'UC Berkeley',
                'focus': '分布偏移',
                'description': '研究模型在测试分布变化时的稳定性界限',
                'google_scholar': 'https://scholar.google.com/citations?user=LKv32bgAAAAJ',
                'website': 'https://jsteinhardt.stat.berkeley.edu/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Steinhardt%2C+Jacob'
            },
            {
                'name': 'Sourav Chatterjee',
                'affiliation': 'Stanford',
                'focus': '高维相变',
                'description': '研究复杂统计系统中的极限分布',
                'google_scholar': 'https://scholar.google.com/citations?user=F6QiwyMAAAAJ',
                'website': 'https://statistics.stanford.edu/people/sourav-chatterjee',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Chatterjee%2C+Sourav'
            },
            {
                'name': 'Lester Mackey',
                'affiliation': 'Microsoft Research',
                'focus': 'Stein 方法',
                'description': '用于评估概率测度之间的统计距离',
                'google_scholar': 'https://scholar.google.com/citations?user=erv7TP0AAAAJ',
                'website': 'https://www.microsoft.com/en-us/research/people/lemackey/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Mackey%2C+Lester'
            },
            {
                'name': 'Pradeep Ravikumar',
                'affiliation': 'CMU',
                'focus': '图模型',
                'description': '高维鲁棒统计与概率图理论',
                'google_scholar': 'https://scholar.google.com/citations?user=Q4DTPw4AAAAJ',
                'website': 'https://www.cs.cmu.edu/~pradeepr/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Ravikumar%2C+Pradeep'
            },
            {
                'name': 'Aditi Raghunathan',
                'affiliation': 'Stanford',
                'focus': '稳健性优化',
                'description': '研究 ICL 在虚假相关下的失效',
                'google_scholar': 'https://scholar.google.com/citations?user=Ch9iRwQAAAAJ',
                'website': 'https://cs.stanford.edu/~adaragh/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Raghunathan%2C+Aditi'
            },
            {
                'name': 'Pascal Massart',
                'affiliation': 'Paris-Saclay',
                'focus': '模型选择',
                'description': '集中不等式理论的领袖',
                'google_scholar': 'https://scholar.google.com/citations?user=KqD0ysMAAAAJ',
                'website': 'https://www.math.u-psud.fr/~massart/',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Massart%2C+Pascal'
            },
            {
                'name': 'Amit Singer',
                'affiliation': 'Princeton',
                'focus': '高维数据组织',
                'description': '大规模数据统计计算的数学框架',
                'google_scholar': 'https://scholar.google.com/citations?user=BNJ1QUAAAAAJ',
                'website': 'https://math.princeton.edu/people/amit-singer',
                'arxiv': 'https://arxiv.org/search/?searchtype=author&query=Singer%2C+Amit'
            }
        ]
    }
}
