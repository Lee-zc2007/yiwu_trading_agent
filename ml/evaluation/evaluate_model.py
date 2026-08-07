import json

from ml.model_registry import model_registry


def main() -> None:
    """无监督模型没有真实标签，输出训练异常率和校准信息供工程验收。"""
    print(json.dumps(model_registry.status(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
