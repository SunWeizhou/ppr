"""
研究领域模板

为统计学和机器学习研究者预设的研究方向和关键词配置。
包含大方向和子领域两级结构。
"""

from typing import Dict, List, Tuple

# ============================================================
# 研究领域模板定义
# ============================================================

RESEARCH_TEMPLATES = {
    # ==================== 统计学 ====================
    "statistical_learning_theory": {
        "name": "统计学习理论",
        "name_en": "Statistical Learning Theory",
        "description": "研究机器学习的统计基础，包括泛化界、样本复杂度等",
        "subfields": {
            "generalization_bounds": {
                "name": "泛化界",
                "keywords": ["generalization bound", "excess risk", "sample complexity",
                            "uniform convergence", "rademacher complexity", "covering number"],
                "weight": 5.0
            },
            "minimax_theory": {
                "name": "Minimax 理论",
                "keywords": ["minimax", "minimax optimal", "minimax rate", "lower bound",
                            "optimal rate", "minimax lower bound"],
                "weight": 5.0
            },
            "pac_bayes": {
                "name": "PAC-Bayes",
                "keywords": ["pac-bayes", "pac bayes", "information theoretic bound",
                            "kl divergence", "prior posterior"],
                "weight": 4.5
            },
            "concentration": {
                "name": "集中不等式",
                "keywords": ["concentration inequality", "concentration bound",
                            "subgaussian", "bernstein", "hoeffding", "mcdiarmid"],
                "weight": 4.0
            },
            "algorithmic_stability": {
                "name": "算法稳定性",
                "keywords": ["algorithmic stability", "stability", "uniform stability",
                            "hypothesis stability"],
                "weight": 4.0
            },
            "vc_theory": {
                "name": "VC 维理论",
                "keywords": ["vc dimension", "shattering", "vapnik chervonenkis",
                            "growth function", "rademacher"],
                "weight": 3.5
            }
        }
    },

    "conformal_prediction": {
        "name": "Conformal Prediction",
        "name_en": "Conformal Prediction",
        "description": "预测集合构建与不确定性量化",
        "subfields": {
            "split_conformal": {
                "name": "Split Conformal",
                "keywords": ["split conformal", "conformal prediction", "prediction set",
                            "coverage guarantee", "finite sample coverage"],
                "weight": 5.0
            },
            "full_conformal": {
                "name": "Full Conformal",
                "keywords": ["full conformal", "conformal inference", "exchangeability"],
                "weight": 5.0
            },
            "conformal_regression": {
                "name": "Conformal 回归",
                "keywords": ["conformal regression", "conformal interval",
                            "prediction interval", "interval estimation"],
                "weight": 4.5
            },
            "conformal_classification": {
                "name": "Conformal 分类",
                "keywords": ["conformal classification", "prediction set classification"],
                "weight": 4.5
            },
            "distribution_free": {
                "name": "分布自由推断",
                "keywords": ["distribution free", "assumption free", "nonparametric inference"],
                "weight": 4.0
            },
            "adaptive_conformal": {
                "name": "自适应 Conformal",
                "keywords": ["adaptive conformal", "weighted conformal", "localized conformal",
                            "covariate shift conformal"],
                "weight": 4.5
            }
        }
    },

    "high_dimensional_statistics": {
        "name": "高维统计",
        "name_en": "High-Dimensional Statistics",
        "description": "高维数据的统计推断方法",
        "subfields": {
            "sparse_estimation": {
                "name": "稀疏估计",
                "keywords": ["sparse estimation", "lasso", "sparse regression",
                            "variable selection", "sparsity"],
                "weight": 5.0
            },
            "high_dimensional_inference": {
                "name": "高维推断",
                "keywords": ["high-dimensional inference", "high dimensional statistics",
                            "p larger than n", "ultrahigh dimensional"],
                "weight": 5.0
            },
            "compressed_sensing": {
                "name": "压缩感知",
                "keywords": ["compressed sensing", "compressive sensing", "sparse recovery",
                            "restricted isometry", "rip"],
                "weight": 4.5
            },
            "random_matrix": {
                "name": "随机矩阵理论",
                "keywords": ["random matrix theory", "random matrix", "eigenvalue distribution",
                            "wishart matrix", "sample covariance"],
                "weight": 4.5
            },
            "high_dim_testing": {
                "name": "高维假设检验",
                "keywords": ["high dimensional testing", "high dimensional test",
                            "multiple testing", "fdr control"],
                "weight": 4.0
            }
        }
    },

    "bayesian_inference": {
        "name": "贝叶斯推断",
        "name_en": "Bayesian Inference",
        "description": "贝叶斯统计推断方法",
        "subfields": {
            "mcmc": {
                "name": "MCMC",
                "keywords": ["mcmc", "markov chain monte carlo", "metropolis hastings",
                            "gibbs sampling", "hamiltonian monte carlo", "hmc"],
                "weight": 5.0
            },
            "variational_inference": {
                "name": "变分推断",
                "keywords": ["variational inference", "variational bayes", "elbo",
                            "mean field", "variational approximation"],
                "weight": 5.0
            },
            "bayesian_nonparametric": {
                "name": "贝叶斯非参数",
                "keywords": ["bayesian nonparametric", "gaussian process", "dirichlet process",
                            "chinese restaurant", "beta process"],
                "weight": 4.5
            },
            "bayesian_optimization": {
                "name": "贝叶斯优化",
                "keywords": ["bayesian optimization", "acquisition function", "gp optimization",
                            "expected improvement", "upper confidence bound"],
                "weight": 4.5
            },
            "posterior_inference": {
                "name": "后验推断",
                "keywords": ["posterior distribution", "posterior inference", "bayesian updating",
                            "prior distribution", "posterior consistency"],
                "weight": 4.0
            }
        }
    },

    "nonparametric_statistics": {
        "name": "非参数统计",
        "name_en": "Nonparametric Statistics",
        "description": "不假设特定分布形式的统计方法",
        "subfields": {
            "kernel_methods": {
                "name": "核方法",
                "keywords": ["kernel method", "kernel estimation", "rkhs",
                            "reproducing kernel", "kernel smoothing"],
                "weight": 4.5
            },
            "density_estimation": {
                "name": "密度估计",
                "keywords": ["density estimation", "kernel density", "nonparametric density"],
                "weight": 4.0
            },
            "nonparametric_regression": {
                "name": "非参数回归",
                "keywords": ["nonparametric regression", "local polynomial",
                            "spline regression", "kernel regression"],
                "weight": 4.5
            },
            "rank_tests": {
                "name": "秩检验",
                "keywords": ["rank test", "nonparametric test", "wilcoxon",
                            "mann whitney", "signed rank"],
                "weight": 3.5
            }
        }
    },

    "causal_inference": {
        "name": "因果推断",
        "name_en": "Causal Inference",
        "description": "因果关系识别和效应估计",
        "subfields": {
            "treatment_effect": {
                "name": "处理效应估计",
                "keywords": ["treatment effect", "causal effect", "average treatment effect",
                            "ate", "heterogeneous treatment", "cate"],
                "weight": 5.0
            },
            "causal_discovery": {
                "name": "因果发现",
                "keywords": ["causal discovery", "dag learning", "causal structure",
                            "skeleton discovery", "pc algorithm"],
                "weight": 4.5
            },
            "instrumental_variable": {
                "name": "工具变量",
                "keywords": ["instrumental variable", "iv estimation", "weak instrument",
                            "two stage least squares"],
                "weight": 4.5
            },
            "propensity_score": {
                "name": "倾向得分",
                "keywords": ["propensity score", "matching", "inverse probability weighting",
                            "doubly robust"],
                "weight": 4.0
            },
            "causal_ml": {
                "name": "因果机器学习",
                "keywords": ["causal machine learning", "double machine learning",
                            "causal forest", "meta learner"],
                "weight": 4.5
            },
            "counterfactual": {
                "name": "反事实推断",
                "keywords": ["counterfactual", "potential outcome", "rubin causal model",
                            "structural equation"],
                "weight": 4.5
            }
        }
    },

    "time_series": {
        "name": "时间序列",
        "name_en": "Time Series",
        "description": "时间序列分析和预测",
        "subfields": {
            "arima": {
                "name": "ARIMA/线性模型",
                "keywords": ["arima", "autoregressive", "time series model",
                            "stationary process", "arma"],
                "weight": 4.0
            },
            "state_space": {
                "name": "状态空间模型",
                "keywords": ["state space model", "kalman filter", "hidden markov",
                            "dynamic linear model"],
                "weight": 4.0
            },
            "nonstationary": {
                "name": "非平稳分析",
                "keywords": ["nonstationary", "unit root", "cointegration",
                            "structural break", "change point"],
                "weight": 4.0
            },
            "spectral_analysis": {
                "name": "谱分析",
                "keywords": ["spectral analysis", "periodogram", "frequency domain",
                            "spectral density"],
                "weight": 3.5
            },
            "long_memory": {
                "name": "长记忆过程",
                "keywords": ["long memory", "fractional integration", "heavy tail",
                            "long range dependence"],
                "weight": 3.5
            }
        }
    },

    "asymptotic_theory": {
        "name": "渐近理论",
        "name_en": "Asymptotic Theory",
        "description": "大样本统计理论",
        "subfields": {
            "asymptotic_normality": {
                "name": "渐近正态性",
                "keywords": ["asymptotic normality", "central limit theorem", "clt",
                            "asymptotic distribution"],
                "weight": 4.5
            },
            "consistency": {
                "name": "一致性理论",
                "keywords": ["consistency", "consistent estimator", "weak consistency",
                            "strong consistency"],
                "weight": 4.0
            },
            "efficiency": {
                "name": "渐近效率",
                "keywords": ["asymptotic efficiency", "fisher information", "crämer rao",
                            "efficient estimator"],
                "weight": 4.0
            },
            "local_asymptotic": {
                "name": "局部渐近理论",
                "keywords": ["local asymptotic", "lan", "contiguity", "local alternatives"],
                "weight": 4.0
            },
            "large_deviations": {
                "name": "大偏差理论",
                "keywords": ["large deviation", "large deviations", "sanov theorem",
                            "rate function"],
                "weight": 4.0
            }
        }
    },

    # ==================== 机器学习理论 ====================
    "deep_learning_theory": {
        "name": "深度学习理论",
        "name_en": "Deep Learning Theory",
        "description": "深度神经网络的理论基础",
        "subfields": {
            "generalization_dl": {
                "name": "深度学习泛化",
                "keywords": ["generalization", "excess risk", "benign overfitting",
                            "sample complexity deep", "uniform convergence neural"],
                "weight": 5.0
            },
            "double_descent": {
                "name": "Double Descent",
                "keywords": ["double descent", "overparameterization", "interpolation",
                            "model wise double descent", "epoch wise double descent"],
                "weight": 5.0
            },
            "implicit_regularization": {
                "name": "隐式正则化",
                "keywords": ["implicit regularization", "implicit bias", "gradient descent bias",
                            "sgd implicit", "edge of stability"],
                "weight": 5.0
            },
            "optimization_landscape": {
                "name": "优化景观",
                "keywords": ["loss landscape", "optimization landscape", "saddle point",
                            "local minima", "mode connectivity", "critical points"],
                "weight": 4.5
            },
            "neural_tangent_kernel": {
                "name": "神经正切核 (NTK)",
                "keywords": ["neural tangent kernel", "ntk", "nngp", "gaussian process",
                            "infinite width network", "lazy training"],
                "weight": 5.0
            },
            "training_dynamics": {
                "name": "训练动力学",
                "keywords": ["training dynamics", "gradient flow", "neural tangent",
                            "learning dynamics", "feature learning"],
                "weight": 4.5
            },
            "grokking": {
                "name": "Grokking 现象",
                "keywords": ["grokking", "sudden generalization", "delayed generalization"],
                "weight": 4.0
            }
        }
    },

    "llm_theory": {
        "name": "大模型/LLM理论",
        "name_en": "Large Language Model Theory",
        "description": "大型语言模型的理论研究",
        "subfields": {
            "in_context_learning": {
                "name": "In-Context Learning",
                "keywords": ["in-context learning", "icl", "context learning",
                            "few-shot learning theory", "prompt learning theory"],
                "weight": 5.0
            },
            "scaling_laws": {
                "name": "Scaling Laws",
                "keywords": ["scaling law", "scaling laws", "compute optimal",
                            "chinchilla", "scaling behavior", "power law scaling"],
                "weight": 5.0
            },
            "emergent_abilities": {
                "name": "涌现能力",
                "keywords": ["emergent ability", "emergence", "emergent capabilities",
                            "phase transition", "sharp transition"],
                "weight": 4.5
            },
            "chain_of_thought": {
                "name": "Chain-of-Thought",
                "keywords": ["chain of thought", "cot", "reasoning", "step-by-step reasoning",
                            "mathematical reasoning llm"],
                "weight": 4.5
            },
            "llm_alignment": {
                "name": "LLM 对齐理论",
                "keywords": ["rlhf", "alignment", "preference learning",
                            "reward modeling", "constitutional ai", "dpo"],
                "weight": 4.5
            },
            "llm_uncertainty": {
                "name": "LLM 不确定性",
                "keywords": ["llm uncertainty", "language model calibration",
                            "confidence estimation", "hallucination detection"],
                "weight": 4.5
            },
            "llm_memorization": {
                "name": "记忆与泛化",
                "keywords": ["memorization", "extraction attack", "privacy llm",
                            "training data extraction"],
                "weight": 4.0
            }
        }
    },

    "transformer_theory": {
        "name": "Transformer 理论",
        "name_en": "Transformer Theory",
        "description": "Transformer 架构的理论分析",
        "subfields": {
            "attention_theory": {
                "name": "注意力机制理论",
                "keywords": ["attention theory", "self-attention", "attention mechanism",
                            "attention matrix", "softmax attention", "attention pattern"],
                "weight": 5.0
            },
            "expressivity": {
                "name": "表达能力",
                "keywords": ["transformer expressivity", "universal approximation transformer",
                            "turing completeness", "transformer representation power"],
                "weight": 4.5
            },
            "ntk_transformer": {
                "name": "Transformer NTK",
                "keywords": ["transformer ntk", "attention kernel", "infinite width transformer"],
                "weight": 4.5
            },
            "transformer_optimization": {
                "name": "Transformer 优化",
                "keywords": ["transformer optimization", "attention gradient",
                            "training transformer theory", "layer normalization theory"],
                "weight": 4.0
            },
            "position_encoding": {
                "name": "位置编码理论",
                "keywords": ["positional encoding", "position embedding",
                            "relative position", "rope", "rotary position"],
                "weight": 4.0
            },
            "efficient_transformer": {
                "name": "高效 Transformer",
                "keywords": ["efficient attention", "linear attention", "sparse attention",
                            "flash attention", "attention complexity"],
                "weight": 4.0
            },
            "length_generalization": {
                "name": "长度泛化",
                "keywords": ["length generalization", "out of distribution transformer",
                            "compositional generalization", "extrapolation"],
                "weight": 4.5
            }
        }
    },

    "optimization_theory": {
        "name": "优化理论",
        "name_en": "Optimization Theory",
        "description": "优化算法的理论分析",
        "subfields": {
            "convex_optimization": {
                "name": "凸优化",
                "keywords": ["convex optimization", "convex analysis", "duality theory",
                            "kkt conditions", "strong duality"],
                "weight": 4.5
            },
            "nonconvex_optimization": {
                "name": "非凸优化",
                "keywords": ["nonconvex optimization", "non-convex", "saddle point",
                            "strict saddle", "no spurious local minima"],
                "weight": 4.5
            },
            "stochastic_optimization": {
                "name": "随机优化",
                "keywords": ["stochastic optimization", "sgd theory", "stochastic gradient",
                            "convergence rate sgd", "variance reduction"],
                "weight": 5.0
            },
            "adaptive_methods": {
                "name": "自适应方法",
                "keywords": ["adam theory", "adaptive gradient", "learning rate adaptation",
                            "convergence adam"],
                "weight": 4.0
            },
            "distributed_optimization": {
                "name": "分布式优化",
                "keywords": ["distributed optimization", "federated optimization",
                            "communication complexity", "local sgd"],
                "weight": 4.0
            },
            "accelerated_methods": {
                "name": "加速方法",
                "keywords": ["accelerated gradient", "nesterov acceleration",
                            "momentum theory", "lower bound optimization"],
                "weight": 4.5
            }
        }
    },

    "reinforcement_learning_theory": {
        "name": "强化学习理论",
        "name_en": "Reinforcement Learning Theory",
        "description": "强化学习的理论基础",
        "subfields": {
            "rl_sample_complexity": {
                "name": "RL 样本复杂度",
                "keywords": ["sample complexity rl", "mdp sample complexity",
                            "rl theory", "sample efficient rl"],
                "weight": 5.0
            },
            "policy_optimization": {
                "name": "策略优化理论",
                "keywords": ["policy gradient theory", "actor critic convergence",
                            "trust region theory", "ppo theory"],
                "weight": 4.5
            },
            "exploration_theory": {
                "name": "探索理论",
                "keywords": ["exploration exploitation", "ucb theory", "thompson sampling",
                            "posterior sampling", "optimism exploration"],
                "weight": 4.5
            },
            "offline_rl": {
                "name": "离线 RL",
                "keywords": ["offline rl", "batch rl", "off policy evaluation",
                            "conservative q learning"],
                "weight": 4.5
            },
            "multi_agent_rl": {
                "name": "多智能体 RL",
                "keywords": ["multi agent reinforcement", "game theory rl",
                            "nash equilibrium rl", "decentralized rl"],
                "weight": 4.0
            }
        }
    },

    "online_learning": {
        "name": "在线学习",
        "name_en": "Online Learning",
        "description": "在线决策和遗憾分析",
        "subfields": {
            "regret_analysis": {
                "name": "遗憾分析",
                "keywords": ["regret bound", "online learning regret",
                            "minimax regret", "adaptive regret"],
                "weight": 5.0
            },
            "online_convex": {
                "name": "在线凸优化",
                "keywords": ["online convex optimization", "oco", "online gradient descent",
                            "follow the regularized leader"],
                "weight": 5.0
            },
            "bandits": {
                "name": "Bandit 问题",
                "keywords": ["multi-armed bandit", "bandit", "regret analysis bandit",
                            "contextual bandit", "linear bandit"],
                "weight": 5.0
            },
            "adversarial_learning": {
                "name": "对抗学习",
                "keywords": ["adversarial online learning", "adversarial bandit",
                            "oblivious adversary", "adaptive adversary"],
                "weight": 4.0
            },
            "prediction_with_experts": {
                "name": "专家预测",
                "keywords": ["prediction with expert advice", "expert aggregation",
                            "weighted majority", "hedge algorithm"],
                "weight": 4.0
            }
        }
    },

    # ==================== 交叉领域 ====================
    "uncertainty_quantification": {
        "name": "不确定性量化",
        "name_en": "Uncertainty Quantification",
        "description": "预测不确定性的量化方法",
        "subfields": {
            "conformal_uq": {
                "name": "Conformal 方法",
                "keywords": ["conformal prediction", "conformal inference",
                            "exchangeability", "prediction set"],
                "weight": 5.0
            },
            "bayesian_uq": {
                "name": "贝叶斯不确定性",
                "keywords": ["bayesian uncertainty", "posterior uncertainty",
                            "bayesian deep learning", "epistemic uncertainty"],
                "weight": 4.5
            },
            "calibration": {
                "name": "校准",
                "keywords": ["calibration", "calibrated prediction", "reliability diagram",
                            "expected calibration error", "temperature scaling"],
                "weight": 4.5
            },
            "ensemble_uncertainty": {
                "name": "集成不确定性",
                "keywords": ["ensemble uncertainty", "deep ensemble", "dropout uncertainty",
                            "mc dropout"],
                "weight": 4.0
            },
            "aleatoric_epistemic": {
                "name": "认知/随机不确定性",
                "keywords": ["aleatoric uncertainty", "epistemic uncertainty",
                            "heteroscedastic", "uncertainty decomposition"],
                "weight": 4.5
            }
        }
    },

    "privacy_preserving_ml": {
        "name": "隐私保护学习",
        "name_en": "Privacy-Preserving ML",
        "description": "保护数据隐私的机器学习方法",
        "subfields": {
            "differential_privacy": {
                "name": "差分隐私",
                "keywords": ["differential privacy", "dp sgd", "privacy accounting",
                            "epsilon delta privacy", "renyi differential privacy"],
                "weight": 5.0
            },
            "federated_learning_theory": {
                "name": "联邦学习理论",
                "keywords": ["federated learning theory", "federated optimization",
                            "local differential privacy", "secure aggregation"],
                "weight": 4.5
            },
            "privacy_utility": {
                "name": "隐私-效用权衡",
                "keywords": ["privacy utility tradeoff", "privacy accuracy",
                            "optimal privacy", "privacy budget"],
                "weight": 4.0
            }
        }
    },

    "graph_neural_networks": {
        "name": "图神经网络",
        "name_en": "Graph Neural Networks",
        "description": "图结构数据的深度学习",
        "subfields": {
            "gnn_expressivity": {
                "name": "GNN 表达能力",
                "keywords": ["gnn expressivity", "weisfeiler lehman", "graph isomorphism",
                            "gnn power", "message passing limit"],
                "weight": 5.0
            },
            "gnn_generalization": {
                "name": "GNN 泛化",
                "keywords": ["gnn generalization", "gnn sample complexity",
                            "graph neural network theory", "over-smoothing"],
                "weight": 4.5
            },
            "gnn_optimization": {
                "name": "GNN 优化",
                "keywords": ["gnn optimization", "graph convolution optimization"],
                "weight": 4.0
            }
        }
    }
}


# ============================================================
# 辅助函数
# ============================================================

def get_all_fields() -> List[Tuple[str, str, str]]:
    """获取所有大方向的列表

    Returns:
        List of (field_key, field_name, description)
    """
    return [
        (key, data["name"], data["description"])
        for key, data in RESEARCH_TEMPLATES.items()
    ]


def get_subfields(field_key: str) -> Dict[str, Dict]:
    """获取某个大方向的所有子领域

    Args:
        field_key: 大方向的键名

    Returns:
        子领域字典 {subfield_key: {name, keywords, weight}}
    """
    field = RESEARCH_TEMPLATES.get(field_key)
    if field:
        return field.get("subfields", {})
    return {}


def get_all_keywords_for_subfields(
    field_key: str,
    subfield_keys: List[str]
) -> Dict[str, Dict]:
    """获取选中子领域的所有关键词

    Args:
        field_key: 大方向键名
        subfield_keys: 子领域键名列表

    Returns:
        关键词字典 {keyword: {weight, category, source}}
    """
    keywords = {}
    subfields = get_subfields(field_key)

    for sf_key in subfield_keys:
        if sf_key in subfields:
            sf = subfields[sf_key]
            weight = sf.get("weight", 4.0)
            for kw in sf.get("keywords", []):
                keywords[kw] = {
                    "weight": weight,
                    "category": "core",
                    "source": f"{field_key}.{sf_key}"
                }

    return keywords


def generate_config_from_selections(
    selected_fields: Dict[str, List[str]],
    custom_keywords: Dict[str, float] = None,
    dislike_keywords: List[str] = None
) -> Dict:
    """根据选择生成完整配置

    Args:
        selected_fields: {field_key: [subfield_keys]}
        custom_keywords: 用户自定义关键词 {keyword: weight}
        dislike_keywords: 不感兴趣的关键词列表

    Returns:
        完整的配置字典
    """
    all_keywords = {}
    theory_keywords = set()

    # 从选中的子领域收集关键词
    for field_key, subfield_keys in selected_fields.items():
        field_keywords = get_all_keywords_for_subfields(field_key, subfield_keys)
        all_keywords.update(field_keywords)

    # 添加自定义关键词
    if custom_keywords:
        for kw, weight in custom_keywords.items():
            all_keywords[kw] = {
                "weight": weight,
                "category": "core" if weight > 0 else "demote",
                "source": "custom"
            }

    # 添加不感兴趣的关键词
    if dislike_keywords:
        for kw in dislike_keywords:
            all_keywords[kw] = {
                "weight": -1.5,
                "category": "dislike",
                "source": "user_dislike"
            }

    # 收集理论关键词
    theory_keywords = [
        "theorem", "proof", "bound", "convergence", "statistical",
        "bayesian", "estimation", "generalization", "asymptotic",
        "minimax", "optimal", "rate", "complexity", "guarantee"
    ]

    return {
        "version": 2,
        "keywords": {
            kw: {"weight": data["weight"], "category": data["category"]}
            for kw, data in all_keywords.items()
        },
        "theory_keywords": theory_keywords,
        "settings": {
            "papers_per_day": 20,
            "lookback_days": 14,
            "pdf_auto_download_score": 2.5,
            "max_papers_per_author": 22,
            "recency_bonus_days": 7,
            "recency_bonus": 0.3,
            "prefer_theory": True,
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
        },
        "sources": {
            "arxiv_enabled": True,
            "journal_enabled": True,
            "scholar_enabled": False,
            "lookback_days": 14
        },
        "zotero": {
            "database_path": "",
            "auto_detect": True,
            "enabled": True
        },
        "venue_priority": {
            "statistics_journals": ["Annals of Statistics", "JASA", "Biometrika", "JRSS-B"],
            "ml_journals": ["JMLR"],
            "top_conferences": ["NeurIPS", "ICML", "ICLR", "COLT", "AISTATS"],
            "theory_conferences": ["COLT", "AISTATS"],
            "statistics_bonus": 1.0,
            "ml_journal_bonus": 0.8,
            "conference_bonus": 0.5,
            "theory_conference_bonus": 1.0
        }
    }


# ============================================================
# 分类显示
# ============================================================

def get_fields_by_category() -> Dict[str, Dict]:
    """按类别获取研究方向

    Returns:
        {category_name: {field_key: field_data}}
    """
    statistics_fields = [
        "statistical_learning_theory", "conformal_prediction",
        "high_dimensional_statistics", "bayesian_inference",
        "nonparametric_statistics", "causal_inference",
        "time_series", "asymptotic_theory"
    ]

    ml_theory_fields = [
        "deep_learning_theory", "llm_theory", "transformer_theory",
        "optimization_theory", "reinforcement_learning_theory",
        "online_learning", "graph_neural_networks"
    ]

    cross_fields = [
        "uncertainty_quantification", "privacy_preserving_ml"
    ]

    return {
        "统计学 (Statistics)": {
            k: RESEARCH_TEMPLATES[k] for k in statistics_fields
            if k in RESEARCH_TEMPLATES
        },
        "机器学习理论 (ML Theory)": {
            k: RESEARCH_TEMPLATES[k] for k in ml_theory_fields
            if k in RESEARCH_TEMPLATES
        },
        "交叉领域 (Cross-disciplinary)": {
            k: RESEARCH_TEMPLATES[k] for k in cross_fields
            if k in RESEARCH_TEMPLATES
        }
    }


if __name__ == "__main__":
    # 测试
    print("=== 研究方向模板 ===\n")

    categories = get_fields_by_category()
    for cat_name, fields in categories.items():
        print(f"\n{cat_name}:")
        for key, data in fields.items():
            print(f"  - {data['name']}: {len(data['subfields'])} 个子领域")
