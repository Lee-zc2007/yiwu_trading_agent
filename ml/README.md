# 异常检测模块

```bash
python -m ml.training.train_isolation_forest
python -m ml.evaluation.evaluate_model
```

`feature_engineering/features.py` 是训练与线上推理共享的唯一特征入口。训练脚本从当前数据库逐客户按时间重放历史，避免使用未来交易特征。模型文件不提交 Git，`metadata.json` 记录版本、特征、样本数、随机种子、污染率和校准分位。
