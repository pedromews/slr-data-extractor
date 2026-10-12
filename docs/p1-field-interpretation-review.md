# P1 field interpretation review — decisions recorded; RLHF provisional

This worksheet records human calibration decisions. The 2026-10-12 alignment applies the approved decisions to schema 4.1-mvp and the P1 reference; RLHF remains provisional pending adviser review. Previous model results are unchanged. Decisions must be based on the paper and intended review scope, not on matching model outputs. This is not final evaluation.

Fill **Human decision** with Include, Exclude or Discuss; record the accepted wording and rationale. Recommendations below apply to the displayed evidence, and can change if additional context supports a different interpretation.

## Decisions to settle first

| Decision | Options | Human decision |
| --- | --- | --- |
| Task/context scope | Application tasks only; or also explicitly fairness-related software pipeline contexts | Application tasks and use contexts only; exclude internal pipeline activities as tasks (confirmed in follow-up). |
| Proposed methods | Include proposed and used methods, preserving claim status (current schema); or restrict scope | Include proposed and used methods, preserving claim status |
| Item granularity | Separate independent categories/techniques; define when an umbrella and examples remain together | Separate independent categories/techniques |
| Specificity | Accept the level stated by authors; do not demand detail absent from the field definition | Accept the level stated by authors |

## Candidate decisions

| ID | Field | Candidate | Assistant suggestion | Rationale | Evidence | Human decision / accepted wording |
| --- | --- | --- | --- | --- | --- | --- |
| B1 | `bias_types` | Gender; ethnicity; age; disability | Include as four items | Explicit discrimination categories; preserve their separation. | [B1](#b1) | Include as four items |
| B2 | `bias_types` | Representation bias | Include | Explicit bias category. Decide whether the field includes representational mechanisms as well as demographic categories. | [B2](#b2) | Include |
| B3 | `bias_types` | Demographic Parity Gap | Exclude from this field | An indicator used to assess fairness, not a named bias category. Consider evaluation_methods instead. | [B3](#b3) | Exclude |
| T1 | `se_tasks_or_contexts` | Classification-based generation | Include under application-context scope | The table explicitly names this application. Do not substitute the metric name for the task. | [T1](#t1) | Include |
| T2 | `se_tasks_or_contexts` | Synthetic data generation | Include under application-context scope | The table connects synthetic data with minority-class representation. | [T2](#t2) | Include |
| T3 | `se_tasks_or_contexts` | Fairness-aware pipeline orchestration | Discuss scope | Explicit fairness connection; qualifies under the current broad pipeline-context definition, but is absent as a task from the narrow reference. | [T3](#t3) | Exclude from this field; retain as a bias source where supported (confirmed in follow-up). |
| T4 | `se_tasks_or_contexts` | Hardware portability and interoperability | Exclude without additional bias connection | The passage supports interoperability, but does not establish the required connection to bias or fairness. | [T4](#t4) | Exclude |
| L1 | `llm_systems` | LLMs / foundational models | Exclude under current definition | Generic architecture categories; the excerpt does not identify a system evaluated as a subject of bias analysis. | [L1](#l1) | Exclude |
| L2 | `llm_systems` | RLHF | Exclude | A training/alignment technique, not a model evaluated as the subject of the study. | [L2](#l2) | Exclude |
| S1 | `bias_sources` | Data; modelling architectures | Include as two items | Explicit origin statement. No further detail is required beyond what the authors provide. | [S1](#s1) | Include as two items |
| S2 | `bias_sources` | Configuration choices; pipeline orchestration; component reuse | Include as three items | Explicit factors that can reintroduce or amplify bias, not necessarily empirically measured causes. | [S2](#s2) | Include as three items |
| S3 | `bias_sources` | Dataset poisoning / adversarial prompts | Exclude on this evidence | The reference-architecture claim concerns resilience; it does not establish these threats as origins of social bias. | [S3](#s3) | Exclude |
| E1 | `evaluation_methods` | Demographic Parity Gap | Include as proposed indicator | The KPI table defines a measurement; its presence does not demonstrate empirical use. | [E1](#e1) | Include |
| E2 | `evaluation_methods` | Differential testing for fairness violations | Include under current definition | Explicit proposed evaluation approach; review whether to add it to the human reference. | [E2](#e2) | Include |
| E3 | `evaluation_methods` | Custom benchmark suites evaluating bias | Include under current definition | Explicit proposed approach for bias evaluation; not evidence of an executed benchmark. | [E3](#e3) | Include |
| E4 | `evaluation_methods` | Latency | Exclude from bias evaluation | General performance metric; sharing a table with fairness indicators does not establish a bias-measurement role. | [E4](#e4) | Exclude |
| I1 | `reported_impacts` | Compromised trustworthiness; reduced societal acceptance | Include; decide one or two items | An asserted consequence, not an empirical measurement in this excerpt. Keep the same unit policy across reference and model review. | [I1](#i1) | Include as two items |
| I2 | `reported_impacts` | Discriminatory outcomes based on sensitive attributes | Include as potential consequence | The authors say can lead to, so preserve the potential nature. | [I2](#i2) | Include |
| I3 | `reported_impacts` | Increased research into AI security | Exclude on this evidence | Attributed to security vulnerabilities rather than explicitly to bias. | [I3](#i3) | Exclude |
| M1 | `mitigation_strategies` | Fairness-aware preprocessing: reweighting / stratified sampling | Include; decide granularity | Explicit bias-mitigation techniques. Decide whether the umbrella and examples form one item or separate techniques. | [M1](#m1) | Include as umbrella, explicitly mentioning both examples |
| M2 | `mitigation_strategies` | RLHF | Discuss required bias linkage | Reference includes it, but this excerpt alone supports a proposed RLHF pipeline. Confirm the contextual link to bias mitigation rather than generic alignment. | [M2](#m2) | Keep provisionally pending adviser review (confirmed in follow-up); explicit bias-reduction linkage remains unresolved. |
| M3 | `mitigation_strategies` | Representative multi-source datasets; domain-specific bias taxonomies | Include as recommendations | Explicit recommendation for fairness; decide whether to retain two independent items. | [M3](#m3) | Include as two independent items |
| M4 | `mitigation_strategies` | Post-quantum cryptography | Exclude on this evidence | Protecting data and fairness metrics from adversaries is not itself evidence of reducing bias. | [M4](#m4) | Exclude |

## Evidence excerpts

Evidence is copied from the prepared catalog; PDF hyphenation is preserved. Pages are physical PDF pages, one-based. Sections are parser labels. IDs provide traceability for this worksheet and are not required human annotations. Table/figure fragments may need surrounding PDF context.

### B1

Page 1; `chunk-0002-e006`; section: I. I NTRODUCTION

> Particularly pressing are the problems of embedded bias- arising from data or modelling architectures - which can lead to discriminatory outcomes based on gender, ethnicity, age or disability.

### B2

Page 2; `chunk-0006-e004`; section: II. D ESIGN PRINCIPLES FOR BIAS -FREE AND AUTO -E VOLVING AI S OFTWARE > A. Principle 1: Fairness-by-Design

> This includes incorporating fairness-aware preprocessing techniques, such as reweighting or stratified sampling, during the data handling stages to address imbalance and represen- tation bias.

### B3

Page 5; `chunk-0020-e005`; section: V. D ISCUSSION

> TABLE I: KPIs for Generative AI Pipelines Category KPI Name Description / Measurement Approach Fairness and Bias Demographic Parity Gap Difference in positive outcomes between sensitive groups (e.g., gender, ethnicity).

### T1

Page 5; `chunk-0020-e008`; section: V. D ISCUSSION

> Measures fairness in classification- based generation.

### T2

Page 5; `chunk-0020-e009`; section: V. D ISCUSSION

> Representation Balance Ratio of minority class samples generated to expected baseline in synthetic data.

### T3

Page 1; `chunk-0003-e007`; section: I. I NTRODUCTION

> However, few approaches focus on integrating fairness-aware strategies at the software engineer- ing level, where configuration choices, pipeline orchestration, and component reuse can reintroduce or amplify biases.

### T4

Page 2; `chunk-0007-e004`; section: II. D ESIGN PRINCIPLES FOR BIAS -FREE AND AUTO -E VOLVING AI S OFTWARE > B. Principle 2: Modular and Evolvable Architecture

> Key architectural features include component abstrac- tion layers that enable interoperability across different models, data modalities, and hardware backends, ensuring a modular and flexible system design.

### L1

Page 3; `chunk-0011-e006`; section: III. R EFERENCE ARCHITECTURE FOR GENERATIVE AI PIPELINES

> • Model Management Layer – Supports training, fine-tuning, versioning, and selection of foundational models, LLMs, or generative architectures.

### L2

Page 4; `chunk-0017-e003`; section: IV. N OVEL METHODS FOR PIPELINE AUTOMATION AND REINFORCEMENT LEARNING INTEGRATION > C. Reinforcement Learning from Human Feedback

> Unlike traditional supervised fine-tuning, RLHF optimises policies based on human preferences and ethical considerations.

### S1

Page 1; `chunk-0002-e006`; section: I. I NTRODUCTION

> Particularly pressing are the problems of embedded bias- arising from data or modelling architectures - which can lead to discriminatory outcomes based on gender, ethnicity, age or disability.

### S2

Page 1; `chunk-0003-e007`; section: I. I NTRODUCTION

> However, few approaches focus on integrating fairness-aware strategies at the software engineer- ing level, where configuration choices, pipeline orchestration, and component reuse can reintroduce or amplify biases.

### S3

Page 1; `chunk-0001-e005`; section: not identified

> We propose a reference architecture that integrates fairness-aware orchestration, explainability mechanisms, and resilience against prompt and dataset poisoning.

### E1

Page 5; `chunk-0020-e005`; section: V. D ISCUSSION

> TABLE I: KPIs for Generative AI Pipelines Category KPI Name Description / Measurement Approach Fairness and Bias Demographic Parity Gap Difference in positive outcomes between sensitive groups (e.g., gender, ethnicity).

### E2

Page 4; `chunk-0018-e004`; section: IV. N OVEL METHODS FOR PIPELINE AUTOMATION AND REINFORCEMENT LEARNING INTEGRATION > D. Automation of Evaluation and Validation

> Differential testing frameworks can compare the results of different model versions or configurations to detect behavioural regressions, fairness violations, or unintended drifts.

### E3

Page 4; `chunk-0018-e005`; section: IV. N OVEL METHODS FOR PIPELINE AUTOMATION AND REINFORCEMENT LEARNING INTEGRATION > D. Automation of Evaluation and Validation

> Custom benchmark suites can be developed to evaluate key generative quality dimensions such as output diversity, coherence, factual accuracy, and bias, ensuring that models meet application-specific performance and ethical criteria.

### E4

Page 5; `chunk-0020-e016`; section: V. D ISCUSSION

> Performance and Efficiency Latency (ms) Average time taken for prompt-to-output generation, including post-processing.

### I1

Page 1; `chunk-0002-e007`; section: I. I NTRODUCTION

> These biases, unless mitigated at the software engineering level, compromise the trustworthiness and soci- etal acceptance of AI applications.

### I2

Page 1; `chunk-0002-e006`; section: I. I NTRODUCTION

> Particularly pressing are the problems of embedded bias- arising from data or modelling architectures - which can lead to discriminatory outcomes based on gender, ethnicity, age or disability.

### I3

Page 2; `chunk-0003-e015`; section: I. I NTRODUCTION

> The vulnerability of AI systems to poisoning attacks, adversarial prompts, and model leakage has prompted increasing research into AI security [12].

### M1

Page 2; `chunk-0006-e004`; section: II. D ESIGN PRINCIPLES FOR BIAS -FREE AND AUTO -E VOLVING AI S OFTWARE > A. Principle 1: Fairness-by-Design

> This includes incorporating fairness-aware preprocessing techniques, such as reweighting or stratified sampling, during the data handling stages to address imbalance and represen- tation bias.

### M2

Page 4; `chunk-0017-e004`; section: IV. N OVEL METHODS FOR PIPELINE AUTOMATION AND REINFORCEMENT LEARNING INTEGRATION > C. Reinforcement Learning from Human Feedback

> The proposed framework can support a complete RLHF pipeline through modular components tailored for generative AI.

### M3

Page 5; `chunk-0022-e010`; section: V. D ISCUSSION

> In- vestment in representative, multi-source datasets and domain- specific bias taxonomies is essential to ensure the long-term fairness and reliability of generative models.

### M4

Page 6; `chunk-0023-e007`; section: V. D ISCUSSION

> The transition to Post-Quantum Crypto- graphic (PQC) standards [14], such as lattice-based or hash- based signatures, must be integrated into the Trust, Safety, and Compliance Layer of the proposed architecture to ensure long- term protection of sensitive training data, human feedback annotations, and fairness metrics against quantum adversaries [15], [16], [17].

## Follow-up after human review

1. Resolve Discuss rows and agree on a consistent unit of extraction.
2. Rewrite concise field definitions in English; do not add article-specific answers.
3. Update and version the reference only after human approval.
4. Freeze a prompt and batch plan for the next comparison; document P1 as a development article.

Source catalog: `runs/pilot-p1-full-article-bias-types-001/prepared/evidence-catalog.json`.

## Applied alignment — 2026-10-12

- Schema revision: 4.0-mvp → 4.1-mvp. Field names and retrieval terms unchanged.
- Output structure remains 4.0-mvp. No prompt, chunking or generation changes.
- Added proposed differential testing and custom benchmark suites to the reference.
- Split the previous Fairness-by-Design umbrella into preprocessing (retaining its two examples), ensemble logic and the existing fairness-checker item. No duplicate checker item added.
- Preserved two independent impacts and two dataset/taxonomy recommendations.
- Removed the extra causal parenthesis from representation bias; evidence and category retained.
- RLHF stays in the reference by explicit user decision, but this is not confirmation that the evidence meets the current explicit-link interpretation. Resolve before final evaluation.
- No schema exception was added just to force extraction of RLHF from P1.
- Reference prior to alignment: `data/references/history/P1-human-reference-before-2026-10-12-alignment.json`.
- Previous reference SHA-256: `8e8ae6791a0f8eca0653f05fa6df2afd65bc26da45a33e5f827a58b87bac066a`.
- Updated reference SHA-256: `20fa45bee00373907e70b0665b27af49a839f3adfa5cf047a2837a1e62a53bd8`.
- Reference revision label (documentation only): `P1-human-reference-2026-10-12`.

Existing evidence entries not affected by approved decisions were left unchanged.
This alignment is not a claim that every reference item has completed final human validation.
