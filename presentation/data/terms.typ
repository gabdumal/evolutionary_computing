// # Terms. Termos.

#import "../packages.typ": quati-abnt.common.components.foreign_text, quati-abnt.common.components.get_term_in_list


// ## Definition. Definição.
#let terms_entries = (
  (
    key: "link",
    short: foreign_text[link],
    short_capitalized: foreign_text[Link],
    plural: foreign_text[links],
    plural_capitalized: foreign_text[Links],
  ),
  (
    key: "script",
    short: foreign_text[script],
    plural: foreign_text[scripts],
  ),
  (
    key: "software",
    short: foreign_text[software],
  ),
  (
    key: "web",
    short: foreign_text[web],
  ),
  (
    key: "api",
    short: [API],
  ),
  (
    key: "dataset",
    short: foreign_text[dataset],
    short_capitalized: foreign_text[Dataset],
    plural: foreign_text[datasets],
    plural_capitalized: foreign_text[Datasets],
  ),
  (
    key: "benchmark",
    short: foreign_text[benchmark],
    short_capitalized: foreign_text[Benchmark],
    plural: foreign_text[benchmarks],
    plural_capitalized: foreign_text[Benchmarks],
  ),
  (
    key: "baseline",
    short: foreign_text[baseline],
    short_capitalized: foreign_text[Baseline],
    plural: foreign_text[baselines],
    plural_capitalized: foreign_text[Baselines],
  ),
  (
    key: "pipeline",
    short: foreign_text[pipeline],
    short_capitalized: foreign_text[Pipeline],
    plural: foreign_text[pipelines],
    plural_capitalized: foreign_text[Pipelines],
  ),
  (
    key: "prompt",
    short: foreign_text[prompt],
    short_capitalized: foreign_text[Prompt],
    plural: foreign_text[prompts],
    plural_capitalized: foreign_text[Prompts],
  ),
  (
    key: "zero_shot",
    short: foreign_text[zero-shot],
    short_capitalized: foreign_text[Zero-shot],
  ),
  (
    key: "few_shot",
    short: foreign_text[few-shot],
    short_capitalized: foreign_text[Few-shot],
  ),
  (
    key: "embedding",
    short: foreign_text[embedding],
    short_capitalized: foreign_text[Embedding],
    plural: foreign_text[embeddings],
    plural_capitalized: foreign_text[Embeddings],
  ),
  (
    key: "weighted_voting",
    short: foreign_text[weighted voting],
    short_capitalized: foreign_text[Weighted voting],
  ),
  (
    key: "out_of_fold",
    short: foreign_text[out-of-fold],
    short_capitalized: foreign_text[Out-of-fold],
  ),
  (
    key: "oversampling",
    short: foreign_text[oversampling],
  ),
  (
    key: "undersampling",
    short: foreign_text[undersampling],
  ),
  (
    key: "one_hot",
    short: foreign_text[one-hot],
    short_capitalized: foreign_text[One-hot],
  ),
  (
    key: "seed",
    short: foreign_text[seed],
    plural: foreign_text[seeds],
    short_capitalized: foreign_text[Seed],
    plural_capitalized: foreign_text[Seeds],
  ),
  (
    key: "fold",
    short: foreign_text[fold],
    plural: foreign_text[folds],
  ),
  (
    key: "outlier",
    short: foreign_text[outlier],
    plural: foreign_text[outliers],
  ),
  (
    key: "accuracy",
    short: foreign_text[accuracy],
    short_capitalized: foreign_text[Accuracy],
  ),
  (
    key: "balanced_accuracy",
    short: foreign_text[balanced accuracy],
    short_capitalized: foreign_text[Balanced accuracy],
  ),
  (
    key: "precision",
    short: foreign_text[precision],
    short_capitalized: foreign_text[Precision],
  ),
  (
    key: "recall",
    short: foreign_text[recall],
    short_capitalized: foreign_text[Recall],
  ),
  (
    key: "f1",
    short: [F1],
  ),
  (
    key: "macro_f1",
    short: [Macro F1],
  ),
  (
    key: "roc_auc",
    short: [ROC-AUC],
  ),
  (
    key: "pr_auc",
    short: [PR-AUC],
  ),
  (
    key: "mcc",
    short: [MCC],
  ),
  (
    key: "hard_voting",
    short: foreign_text[hard voting],
    short_capitalized: foreign_text[Hard voting],
  ),
  (
    key: "hard_voting_ponderado",
    short: [#foreign_text[hard voting] ponderado],
    short_capitalized: [#foreign_text[Hard voting] ponderado],
  ),
  (
    key: "soft_voting",
    short: foreign_text[soft voting],
    short_capitalized: foreign_text[Soft voting],
  ),
  (
    key: "soft_voting_ponderado",
    short: [#foreign_text[soft voting] ponderado],
    short_capitalized: [#foreign_text[Soft voting] ponderado],
  ),
  (
    key: "fitness",
    short: foreign_text[fitness],
  ),
  (
    key: "seeking",
    short: foreign_text[seeking],
    short_capitalized: foreign_text[Seeking],
  ),
  (
    key: "tracing",
    short: foreign_text[tracing],
    short_capitalized: foreign_text[Tracing],
  ),
  (
    key: "za",
    short: [ZO-AdaMM],
  ),
  (
    key: "best",
    short: foreign_text[best],
    short_capitalized: foreign_text[Best],
  ),
)


// ## Access. Acesso.
#let get_term = (
  capitalize: false,
  field: "short",
  plural: false,
  term_key,
) => {
  get_term_in_list(
    capitalize: capitalize,
    field: field,
    plural: plural,
    terms_entries: terms_entries,
    term_key,
  )
}
