// # Glossary. Glossário.

#import "../components.typ": *

#let abbreviations_entries = (
  (
    key: "abnt",
    short: "ABNT",
    long: "Associação Brasileira de Normas Técnicas",
    // group: "Normatização",
  ),
  (
    key: "nbr",
    short: "NBR",
    plural: "NBRs",
    long: "Norma Brasileira",
    longplural: "Normas Brasileiras",
    // group: "Normatização",
  ),
  (
    key: "ssh",
    short: "SSH",
    long: foreign_text[Secure Shell],
  ),
  (
    key: "api",
    short: "API",
    long: "Application Programming Interface",
    // group: "Computação",
  ),
  (
    key: "csv",
    short: "CSV",
    long: "Comma-Separated Values",
    // group: "Dados",
  ),
  (
    key: "cpu",
    short: "CPU",
    plural: "CPUs",
    long: "Central Processing Unit",
    // group: "Hardware",
  ),
  (
    key: "gpu",
    short: "GPU",
    plural: "GPUs",
    long: "Graphics Processing Unit",
    // group: "Hardware",
  ),
  (
    key: "gpt",
    short: "GPT",
    plural: "GPTs",
    long: "Generative Pre-trained Transformer",
    // group: "Modelos de linguagem",
  ),
  (
    key: "llm",
    short: "LLM",
    plural: "LLMs",
    long: "grande modelo de linguagem",
    longplural: "grandes modelos de linguagem",
    description: [Em inglês, #foreign_text[Large Language Model].],
    // group: "Modelos de linguagem",
  ),
  (
    key: "mcc",
    short: "MCC",
    long: "Matthews Correlation Coefficient",
    // group: "Avaliação",
  ),
  (
    key: "auc_roc",
    short: "AUC-ROC",
    long: "Area Under the Receiver Operating Characteristic Curve",
    // group: "Avaliação",
  ),
  (
    key: "auc_pr",
    short: "AUC-PR",
    long: "Area Under the Precision-Recall Curve",
    // group: "Avaliação",
  ),
  (
    key: "svm",
    short: "SVM",
    long: "máquina de vetores de suporte",
    description: [Em inglês, #foreign_text[Support Vector Machine].],
    // group: "Aprendizado de máquina",
  ),
  (
    key: "som",
    short: "SOM",
    long: "mapa auto-organizável",
    description: [Em inglês, #foreign_text[Self-Organizing Map].],
    // group: "Aprendizado de máquina",
  ),
  (
    key: "cso",
    short: "CSO",
    long: foreign_text[Cat Swarm Optimization],
  ),
)

#let glossary_entries = (
  (
    key: "rn",
    short: "rede neural",
    plural: "redes neurais",
    custom: foreign_text[neural network],
    description: [Em inglês, #foreign_text[neural network]. Modelo computacional composto por camadas de unidades interligadas que aprendem padrões em dados por meio de ajustes de pesos @li:2022:survey_convolutional_neural_networks.],
    // group: "Computação",
  ),
  (
    key: "machine_learning",
    short: "aprendizado de máquina",
    custom: foreign_text[machine learning],
    description: [Área da computação que desenvolve métodos capazes de aprender padrões a partir de dados para realizar tarefas como classificação, regressão e agrupamento.],
    // group: "Aprendizado de máquina",
  ),
  (
    key: "aprendizado_supervisionado",
    short: "aprendizado supervisionado",
    custom: foreign_text[supervised learning],
    description: [Paradigma de aprendizado em que o modelo é ajustado a partir de exemplos associados a respostas ou rótulos conhecidos.],
    // group: "Aprendizado de máquina",
  ),
  (
    key: "classificação_binária",
    short: "classificação binária",
    custom: foreign_text[binary classification],
    description: [Tarefa de classificação em que cada observação deve ser atribuída a apenas uma entre duas classes possíveis.],
    // group: "Aprendizado de máquina",
  ),
  (
    key: "classificação_multiclasse",
    short: "classificação multiclasse",
    custom: foreign_text[multiclass classification],
    description: [Tarefa de classificação em que cada observação deve ser atribuída a uma entre três ou mais classes possíveis.],
    // group: "Aprendizado de máquina",
  ),
  (
    key: "decision_tree",
    short: "árvore de decisão",
    sort: "arvore de decisao",
    plural: "árvores de decisão",
    custom: foreign_text[decision tree],
    description: [Modelo de aprendizado que representa decisões por meio de uma estrutura hierárquica de divisões sucessivas do espaço de características.],
    // group: "Aprendizado de máquina",
  ),
  (
    key: "random_forest",
    short: "floresta aleatória",
    plural: "florestas aleatórias",
    custom: foreign_text[random forest],
    description: [Método de comitê que combina múltiplas árvores de decisão construídas com fontes de aleatoriedade na amostragem das observações e na seleção das características.],
    // group: "Aprendizado de máquina",
  ),
  (
    key: "gradient_boosting",
    short: foreign_text[gradient boosting],
    custom: foreign_text[gradient boosting],
    description: [Método de comitê que adiciona modelos sequencialmente, buscando reduzir os erros acumulados pelos modelos anteriores.],
    // group: "Aprendizado de máquina",
  ),
  (
    key: "xgboost",
    short: "XGBoost",
    description: [Implementação de aprendizado por comitê baseada em árvores e na estratégia de gradient boosting, utilizada neste trabalho como um dos modelos de referência.],
    // group: "Aprendizado de máquina",
  ),
  (
    key: "zero_shot",
    short: "zero-shot",
    custom: foreign_text[zero-shot],
    description: [Uso de um modelo de linguagem para realizar uma tarefa sem fornecer exemplos específicos da tarefa no contexto do prompt.],
    // group: "Modelos de linguagem",
  ),
  (
    key: "few_shot",
    short: "few-shot",
    custom: foreign_text[few-shot],
    description: [Uso de um modelo de linguagem para realizar uma tarefa após receber no prompt uma pequena quantidade de exemplos da tarefa.],
    // group: "Modelos de linguagem",
  ),
  (
    key: "embedding",
    short: "embedding",
    plural: "embeddings",
    description: [Representação vetorial de um objeto ou unidade de informação, construída de modo a codificar características ou relações úteis para tarefas computacionais.],
    // group: "Modelos de linguagem",
  ),
  (
    key: "class_imbalance",
    short: "desbalanceamento de classes",
    custom: foreign_text[class imbalance],
    description: [Situação em que as classes de um conjunto de dados apresentam quantidades de observações significativamente diferentes, fazendo com que algumas classes sejam representadas com muito mais frequência que outras.],
    // group: "Dados",
  ),
  (
    key: "data_leakage",
    short: "vazamento de dados",
    custom: foreign_text[data leakage],
    description: [Situação em que informações que não deveriam estar disponíveis durante o treinamento influenciam o ajuste ou a avaliação de um modelo, podendo produzir estimativas de desempenho artificialmente otimistas.],
    // group: "Metodologia",
  ),
  (
    key: "one_hot",
    short: [codificação #foreign_text[one-hot]],
    custom: foreign_text[one-hot encoding],
    description: [Forma de representar uma variável categórica por meio de múltiplas variáveis binárias, com uma variável associada a cada categoria representada.],
    // group: "Dados",
  ),
  (
    key: "f_score",
    short: "F-score",
    custom: foreign_text[F-score],
    description: [Medida que combina precisão e revocação por meio de sua média harmônica, podendo ser parametrizada para atribuir pesos diferentes a essas duas medidas.],
    // group: "Avaliação",
  ),
  (
    key: "confusion_matrix",
    short: "matriz de confusão",
    custom: foreign_text[confusion matrix],
    description: [Tabela que organiza, para um problema de classificação, as contagens das classes verdadeiras em relação às classes previstas pelo modelo.],
    // group: "Avaliação",
  ),
)

#let symbols_entries = ()


#let glossaries_entries = (
  ..abbreviations_entries,
  ..glossary_entries,
  ..symbols_entries,
)
