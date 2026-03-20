# RRF Zero-Hit Failures — Bottom 25% Queries

All 81 queries below scored **NDCG@10 = 0** — RRF retrieved zero relevant documents in the top-10.

Dataset: BEIR NFCorpus (3,633 medical/nutrition documents)

---

## Summary

| Stat | Value |
|---|---|
| Queries with NDCG=0 | 81 / 323 (25%) |
| Total relevant docs missed | 1114 |
| FTS5 returned nothing | 46 queries |
| Relevant docs not in FTS nor vec top-100 | 1001 |
| Relevant docs in vec top-100 only (RRF ranked too low) | 99 |
| Relevant docs in both top-100 (pure fusion fail) | 6 |

---

## Root Cause Categories

| Category | Description | Queries affected | Docs missed |
|---|---|---|---|
| A | FTS5 returned nothing (vocabulary mismatch) | **46 queries** (57%) | — |
| B | Relevant doc not in FTS nor vec top-100 (recall ceiling) | **77 queries** (95%) | **1,001 docs** |
| C | Both indexes found it but RRF fusion ranked it below top-10 | **5 queries** (6%) | **6 docs** |
| — | Vec top-100 only, not FTS (RRF score diluted) | across many queries | **99 docs** |

Note: categories overlap — a single query can have failures from multiple categories.
- **45 queries** failed purely due to Category B (recall failure only, no fusion issue)
- **Only 1 query** failed purely due to Category C (fusion failure only)
- **23 queries** had FTS5 return nothing AND all relevant docs were outside both top-100

### Category A — FTS5 returned nothing (46 queries, 57% of failures)
Query terms have no keyword match in the corpus at all. FTS5 uses exact token matching — queries with medical jargon, brand names, or unusual phrasing return an empty result set. Vector search ran alone but wasn't sufficient.

**Implication:** A semantic-first retriever (dense retrieval / ColBERT v2) would not suffer this — it encodes meaning, not exact tokens.

### Category B — Relevant docs outside both top-100 candidates (77 queries, 1,001 docs missed)
Neither FTS5 nor vector search retrieved the relevant doc in their top-100 candidates. **This is the dominant failure mode.** RRF never had a chance to surface these — you cannot fuse what was never retrieved.

**Implication:** The 100-candidate ceiling is too tight. Options: (1) expand to top-200/500, (2) use a better first-stage retriever trained for recall (DPR, ColBERT v2), (3) query expansion.

### Category C — Fusion score too low (5 queries, 6 docs missed)
Both FTS5 and vector search retrieved the relevant doc in their top-100, but the RRF weighted combination ranked it outside the top-10. This is a pure fusion/weighting failure.

**Implication:** Tuning RRF weights or using learned fusion could fix these — but this affects only 5 queries, so it is the least impactful category.

---

## All 81 Zero-Hit Queries

| # | Query | Relevant Docs | FTS5 hit | Vec hit | Missed in neither | Vec-only misses | Fusion fails |
|---|---|---|---|---|---|---|---|
| 1 | What Do Meat Purge and Cola Have in Common? | 62 | **NO** | yes | 53 | 9 | 0 |
| 2 | Increasing Muscle Strength with Fenugreek | 40 | **NO** | yes | 40 | 0 | 0 |
| 3 | How Chemically Contaminated Are We? | 54 | **NO** | yes | 52 | 2 | 0 |
| 4 | Breast Cancer and Diet | 42 | yes | yes | 33 | 6 | 2 |
| 5 | Didn't another study show carnitine was good for the heart? | 3 | **NO** | yes | 3 | 0 | 0 |
| 6 | What about pepper plus turmeric in V8 juice? | 3 | **NO** | yes | 3 | 0 | 0 |
| 7 | How can you believe in any scientific study? | 5 | **NO** | yes | 5 | 0 | 0 |
| 8 | accidents | 1 | yes | yes | 1 | 0 | 0 |
| 9 | Alli | 1 | **NO** | yes | 1 | 0 | 0 |
| 10 | amnesia | 2 | **NO** | yes | 1 | 1 | 0 |
| 11 | antinutrients | 44 | **NO** | yes | 42 | 2 | 0 |
| 12 | Arkansas | 1 | yes | yes | 1 | 0 | 0 |
| 13 | bagels | 29 | **NO** | yes | 28 | 1 | 0 |
| 14 | bioavailability | 21 | yes | yes | 20 | 0 | 0 |
| 15 | BRCA genes | 7 | yes | yes | 7 | 0 | 0 |
| 16 | Bush administration | 2 | yes | yes | 2 | 0 | 0 |
| 17 | canker sores | 1 | **NO** | yes | 0 | 1 | 0 |
| 18 | chanterelle mushrooms | 1 | yes | yes | 1 | 0 | 0 |
| 19 | coma | 31 | yes | yes | 29 | 0 | 1 |
| 20 | cortisol | 3 | yes | yes | 2 | 0 | 0 |
| 21 | cumin | 3 | yes | yes | 2 | 0 | 0 |
| 22 | Czechoslovakia | 2 | **NO** | yes | 2 | 0 | 0 |
| 23 | deafness | 5 | **NO** | yes | 5 | 0 | 0 |
| 24 | dietary scoring | 1 | yes | yes | 0 | 1 | 0 |
| 25 | Dr. Walter Willett | 9 | **NO** | yes | 9 | 0 | 0 |
| 26 | eggnog | 5 | **NO** | yes | 4 | 1 | 0 |
| 27 | energy drinks | 11 | yes | yes | 11 | 0 | 0 |
| 28 | fava beans | 1 | **NO** | yes | 1 | 0 | 0 |
| 29 | flax oil | 18 | yes | yes | 12 | 6 | 0 |
| 30 | Fosamax | 17 | **NO** | yes | 17 | 0 | 0 |
| 31 | genetic manipulation | 4 | **NO** | yes | 4 | 0 | 0 |
| 32 | halibut | 4 | **NO** | yes | 4 | 0 | 0 |
| 33 | Harvard Physicians’ Study II | 6 | **NO** | yes | 3 | 3 | 0 |
| 34 | hearing | 1 | yes | yes | 1 | 0 | 0 |
| 35 | hernia | 4 | yes | yes | 3 | 1 | 0 |
| 36 | hormonal dysfunction | 26 | **NO** | yes | 20 | 6 | 0 |
| 37 | industrial toxins | 253 | **NO** | yes | 232 | 21 | 0 |
| 38 | Iowa Women’s Health Study | 6 | yes | yes | 6 | 0 | 0 |
| 39 | kohlrabi | 1 | yes | yes | 0 | 0 | 0 |
| 40 | lard | 54 | yes | yes | 52 | 2 | 0 |
| 41 | leeks | 1 | **NO** | yes | 1 | 0 | 0 |
| 42 | Lindane | 2 | yes | yes | 2 | 0 | 0 |
| 43 | mesquite | 6 | **NO** | yes | 6 | 0 | 0 |
| 44 | Mevacor | 4 | **NO** | yes | 4 | 0 | 0 |
| 45 | molasses | 6 | yes | yes | 5 | 0 | 0 |
| 46 | mouth cancer | 28 | yes | yes | 22 | 5 | 1 |
| 47 | National Academy of Sciences | 4 | yes | yes | 4 | 0 | 0 |
| 48 | okra | 1 | **NO** | yes | 1 | 0 | 0 |
| 49 | oxen meat | 2 | **NO** | yes | 2 | 0 | 0 |
| 50 | Peoria | 3 | **NO** | yes | 3 | 0 | 0 |
| 51 | pineapples | 7 | **NO** | yes | 4 | 3 | 0 |
| 52 | plant-based diet | 36 | yes | yes | 35 | 1 | 0 |
| 53 | poisonous plants | 4 | **NO** | yes | 2 | 2 | 0 |
| 54 | pumpkin | 13 | yes | yes | 13 | 0 | 0 |
| 55 | quinine | 11 | yes | yes | 9 | 2 | 0 |
| 56 | red tea | 11 | yes | yes | 9 | 2 | 0 |
| 57 | rickets | 3 | yes | yes | 2 | 0 | 0 |
| 58 | Rutin | 6 | yes | yes | 5 | 0 | 1 |
| 59 | shelf life | 1 | yes | yes | 0 | 0 | 1 |
| 60 | soil health | 1 | yes | yes | 1 | 0 | 0 |
| 61 | Splenda | 12 | **NO** | yes | 12 | 0 | 0 |
| 62 | subsidies | 1 | yes | yes | 1 | 0 | 0 |
| 63 | taro | 2 | **NO** | yes | 2 | 0 | 0 |
| 64 | thiamine | 7 | yes | yes | 7 | 0 | 0 |
| 65 | Tufts | 10 | **NO** | yes | 9 | 1 | 0 |
| 66 | turnips | 1 | **NO** | yes | 1 | 0 | 0 |
| 67 | ultra-processed foods | 5 | **NO** | yes | 4 | 1 | 0 |
| 68 | veal | 2 | yes | yes | 2 | 0 | 0 |
| 69 | veggie chicken | 5 | **NO** | yes | 4 | 1 | 0 |
| 70 | vitamin K | 2 | yes | yes | 2 | 0 | 0 |
| 71 | weight gain | 15 | yes | yes | 15 | 0 | 0 |
| 72 | whiting | 2 | **NO** | yes | 1 | 1 | 0 |
| 73 | Yale | 18 | **NO** | yes | 18 | 0 | 0 |
| 74 | Zoloft | 5 | **NO** | yes | 3 | 2 | 0 |
| 75 | More Than an Apple a Day: Combating Common Diseases | 21 | **NO** | yes | 21 | 0 | 0 |
| 76 | Barriers to Heart Disease Prevention | 25 | **NO** | yes | 19 | 6 | 0 |
| 77 | Apple Juice May Be Worse Than Sugar Water | 8 | **NO** | yes | 5 | 3 | 0 |
| 78 | Preventing Strokes with Diet | 8 | **NO** | yes | 6 | 2 | 0 |
| 79 | Benefits of Fenugreek Seeds | 17 | **NO** | yes | 16 | 1 | 0 |
| 80 | More Antibiotics In White Meat or Dark Meat? | 9 | **NO** | yes | 7 | 2 | 0 |
| 81 | Filled Full of Lead | 5 | **NO** | yes | 4 | 1 | 0 |

---

## Detailed Breakdown — Top 20 by Relevant Doc Count

These are the queries with the most relevant docs that RRF completely failed on.

### "industrial toxins"

- **Relevant docs in corpus:** 253
- **NDCG@10:** 0.0
- **FTS5 returned results:** NO - vocabulary mismatch
- **Missed - not in FTS nor vec top-100:** 232
- **Missed - vec top-100 only (RRF ranked too low):** 21
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.013115)* Manufactured uncertainty: protecting public health in the age of contested science and product defense. The strategy of "manufacturing uncertainty" has been use...
2. *(score=0.012983)* Clostridium difficile in Retail Meat Products, USA, 2007 To determine the presence of Clostridium difficile, we sampled cooked and uncooked meat products sold i...
3. *(score=0.012855)* Airborne mutagens produced by frying beef, pork and a soy-based food. Airborne cooking by-products from frying beef (hamburgers), pork (bacon strips) and soybea...
4. *(score=0.012731)* First detection of anatoxin-a in human and animal dietary supplements containing cyanobacteria. Anatoxin-a is a potent neurotoxin produced by several species of...
5. *(score=0.01261)* Popcorn-worker lung caused by corporate and regulatory negligence: an avoidable tragedy. Diacetyl-containing butter flavor was identified as the cause of an out...

**Sample missed relevant docs:**

- [rel=1, found in: vec top-100] Cancer and non-cancer health effects from food contaminant exposures for children and adults in California: a risk assessment Background In the absence of curre...
- [rel=1, found in: neither index] Prenatal exposure to polychlorinated biphenyls and dioxins from the maternal diet may be associated with immunosuppressive effects that persist int... We invest...
- [rel=1, found in: neither index] Fish intake and breastfeeding time are associated with serum concentrations of organochlorines in a Swedish population. Persistent organic pollutants (POPs) exe...

---

### "What Do Meat Purge and Cola Have in Common?"

- **Relevant docs in corpus:** 62
- **NDCG@10:** 0.0
- **FTS5 returned results:** NO - vocabulary mismatch
- **Missed - not in FTS nor vec top-100:** 53
- **Missed - vec top-100 only (RRF ranked too low):** 9
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.013115)* Reducing the fat content in ground beef without sacrificing quality: a review. Americans are becoming more health conscious in their food choices and many are i...
2. *(score=0.012983)* Survey of naturally and conventionally cured commercial frankfurters, ham, and bacon for physio-chemical characteristics that affect bacterial growth. Natural a...
3. *(score=0.012855)* Applying morphologic techniques to evaluate hotdogs: what is in the hotdogs we eat? Americans consume billions of hotdogs per year resulting in more than a bill...
4. *(score=0.012731)* Microbiology of fresh and restructured lamb meat: a review. Microbiology of meats has been a subject of great concern in food science and public health in recen...
5. *(score=0.01261)* Beyond celery and starter culture: advances in natural/organic curing processes in the United States. Over the past 10years there has been ongoing development o...

**Sample missed relevant docs:**

- [rel=2, found in: neither index] Public health impact of dietary phosphorus excess on bone and cardiovascular health in the general population. This review explores the potential adverse impact...
- [rel=2, found in: neither index] Phosphate Additives in Food—a Health Risk Background Hyperphosphatemia has been identified in the past decade as a strong predictor of mortality in advanced chr...
- [rel=2, found in: neither index] Differences among total and in vitro digestible phosphorus content of plant foods and beverages. OBJECTIVE: Among plant foods, grain products, legumes, and seed...

---

### "How Chemically Contaminated Are We?"

- **Relevant docs in corpus:** 54
- **NDCG@10:** 0.0
- **FTS5 returned results:** NO - vocabulary mismatch
- **Missed - not in FTS nor vec top-100:** 52
- **Missed - vec top-100 only (RRF ranked too low):** 2
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.013115)* Polybrominated diphenyl ethers in food and human dietary exposure: a review of the recent scientific literature. Polybrominated diphenyl ethers (PBDEs) are a cl...
2. *(score=0.012983)* Perfluorinated Compounds, Polychlorinated Biphenyls, and Organochlorine Pesticide Contamination in Composite Food Samples from Dallas, Texas, USA Objectives The...
3. *(score=0.012855)* Brominated flame retardants in US food. We and others recently began studying brominated flame retardant levels in various matrices in the US including human mi...
4. *(score=0.012731)* Radioactive fallout in the United States due to the Fukushima nuclear plant accident. The release of radioactivity into the atmosphere from the damaged Fukushim...
5. *(score=0.01261)* The environmental and public health risks associated with arsenical use in animal feeds. Arsenic exposures contribute significantly to the burden of preventable...

**Sample missed relevant docs:**

- [rel=1, found in: neither index] The effect of dietary factors on nitrosoproline levels in human urine. The effect of dietary components on the levels of nitrosoproline ( NPRO ) excreted over a...
- [rel=1, found in: neither index] Understanding tobacco smoke carcinogen NNK and lung tumorigenesis. The deleterious effects of tumor-promoting tobacco carcinogen, nitrosamine 4-(methylnitrosami...
- [rel=1, found in: neither index] Determination of total N-nitroso compounds and their precursors in frankfurters, fresh meat, dried salted fish, sauces, tobacco, and tobacco smoke ... Total N-n...

---

### "lard"

- **Relevant docs in corpus:** 54
- **NDCG@10:** 0.0
- **FTS5 returned results:** yes
- **Missed - not in FTS nor vec top-100:** 52
- **Missed - vec top-100 only (RRF ranked too low):** 2
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.013035)* Gastroenterology in ancient Egypt. Physicians in ancient Egypt devoted their care to disorders of individual organs. Notable among the specialties was gastroent...
2. *(score=0.012903)* No Association of Coffee Consumption with Gastric Ulcer, Duodenal Ulcer, Reflux Esophagitis, and Non-Erosive Reflux Disease: A Cross-Sectional Study of 8,013 He...
3. *(score=0.012775)* An understanding of excessive intestinal gas. Complaints of "excessive gas" from patients are very common but are difficult, if not impossible, for the physicia...
4. *(score=0.012651)* The effect of oral alpha-galactosidase on intestinal gas production and gas-related symptoms. Bloating, abdominal distention, and flatulence represent very freq...
5. *(score=0.012531)* The development of the concept of dietary fiber in human nutrition. Fundamental studies of the laxative action of wheat bran were undertaken in the United State...

**Sample missed relevant docs:**

- [rel=1, found in: neither index] p-Nonyl-phenol: an estrogenic xenobiotic released from "modified" polystyrene. Alkylphenols are widely used as plastic additives and surfactants. We report the ...
- [rel=1, found in: neither index] Do fast foods cause asthma, rhinoconjunctivitis and eczema? Global findings from the International Study of Asthma and Allergies in Childhood (ISAA... BACKGROUN...
- [rel=1, found in: neither index] Alkylphenols in human milk and their relations to dietary habits in central Taiwan. The aims of this study were to determine the concentrations of 4-nonylphenol...

---

### "antinutrients"

- **Relevant docs in corpus:** 44
- **NDCG@10:** 0.0
- **FTS5 returned results:** NO - vocabulary mismatch
- **Missed - not in FTS nor vec top-100:** 42
- **Missed - vec top-100 only (RRF ranked too low):** 2
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.013115)* Whole grains and human health. Epidemiological studies find that whole-grain intake is protective against cancer, CVD, diabetes, and obesity. Despite recommenda...
2. *(score=0.012983)* Fostering antioxidant defences: up-regulation of antioxidant genes or antioxidant supplementation? Vitamins have traditionally been considered as food component...
3. *(score=0.012855)* Phytonutrient intake by adults in the United States in relation to fruit and vegetable consumption. BACKGROUND: Individuals consuming diets dense in fruits and ...
4. *(score=0.012731)* Phytonutrient intake by adults in the United States in relation to fruit and vegetable consumption. BACKGROUND: Individuals consuming diets dense in fruits and ...
5. *(score=0.01261)* Proposal for a dietary "phytochemical index". There is ample reason to believe that diets rich in phytochemicals provide protection from vascular diseases and m...

**Sample missed relevant docs:**

- [rel=1, found in: neither index] The effect of inositol hexaphosphate on the expression of selected metalloproteinases and their tissue inhibitors in IL-1β-stimulated colon cancer cells Introdu...
- [rel=1, found in: neither index] High Dry Bean Intake and Reduced Risk of Advanced Colorectal Adenoma Recurrence among Participants in the Polyp Prevention Trial Adequate fruit and vegetable in...
- [rel=1, found in: neither index] Efficacy of IP6 + inositol in the treatment of breast cancer patients receiving chemotherapy: prospective, randomized, pilot clinical study Background Prospecti...

---

### "Breast Cancer and Diet"

- **Relevant docs in corpus:** 42
- **NDCG@10:** 0.0
- **FTS5 returned results:** yes
- **Missed - not in FTS nor vec top-100:** 33
- **Missed - vec top-100 only (RRF ranked too low):** 6
- **Missed - in both top-100 (fusion failed):** 2

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.013035)* Diet and breast cancer: understanding risks and benefits. BACKGROUND: Breast cancer is the most commonly diagnosed cancer among women in the United States. Exte...
2. *(score=0.012574)* Post-diagnosis dietary factors and survival after invasive breast cancer Little is known about the effects of diet after breast cancer diagnosis on survival. We...
3. *(score=0.012119)* Influence of a Diet Very High in Vegetables, Fruit, and Fiber and Low in Fat on Prognosis Following Treatment for Breast Cancer Context Evidence is lacking that...
4. *(score=0.011444)* Empirically derived dietary patterns and risk of postmenopausal breast cancer in a large prospective cohort study. BACKGROUND: Inconsistent associations have be...
5. *(score=0.011425)* Low-fat dietary pattern and risk of benign proliferative breast disease: a randomized, controlled dietary modification trial Modifiable factors, including diet,...

**Sample missed relevant docs:**

- [rel=1, found in: neither index] Phytochemicals for breast cancer prevention by targeting aromatase. Aromatase is a cytochrome P450 enzyme (CYP19) and is the rate limiting enzyme in the convers...
- [rel=1, found in: neither index] Hormonal growth promoting agents in food producing animals. In contrast to the use of hormonal doping agents in sports to enhance the performance of athletes, i...
- [rel=1, found in: neither index] Body fat and animal protein intakes are associated with adrenal androgen secretion in children. BACKGROUND: Adrenarche is the increase in adrenal androgen (AA) ...

---

### "Increasing Muscle Strength with Fenugreek"

- **Relevant docs in corpus:** 40
- **NDCG@10:** 0.0
- **FTS5 returned results:** NO - vocabulary mismatch
- **Missed - not in FTS nor vec top-100:** 40
- **Missed - vec top-100 only (RRF ranked too low):** 0
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.013115)* Statin therapy induces ultrastructural damage in skeletal muscle in patients without myalgia. Muscle pain and weakness are frequent complaints in patients recei...
2. *(score=0.012983)* Massage therapy attenuates inflammatory signaling after exercise-induced muscle damage. Massage therapy is commonly used during physical rehabilitation of skele...
3. *(score=0.012855)* Creatine: are the benefits worth the risk? Creatine monohydrate is a popular sports supplement used to maintain levels of high-energy phosphates during exercise...
4. *(score=0.012731)* Supplementation with vitamin C and N-acetyl-cysteine increases oxidative stress in humans after an acute muscle injury induced by eccentric exercise. There has ...
5. *(score=0.01261)* Exercise and longevity. Aging is a natural and complex physiological process influenced by many factors, some of which are modifiable. As the number of older in...

**Sample missed relevant docs:**

- [rel=1, found in: neither index] Amla (Emblica officinalis Gaertn), a wonder berry in the treatment and prevention of cancer. Emblica officinalis Gaertn. or Phyllanthus emblica Linn, commonly k...
- [rel=1, found in: neither index] Pseudo-maple syrup urine disease due to maternal prenatal ingestion of fenugreek. Fenugreek, maple syrup and the urine of maple syrup urine disease (MSUD) patie...
- [rel=1, found in: neither index] Effects of a low-fat, high-fiber diet and exercise program on breast cancer risk factors in vivo and tumor cell growth and apoptosis in vitro. The present study...

---

### "plant-based diet"

- **Relevant docs in corpus:** 36
- **NDCG@10:** 0.0
- **FTS5 returned results:** yes
- **Missed - not in FTS nor vec top-100:** 35
- **Missed - vec top-100 only (RRF ranked too low):** 1
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.012983)* Effects of plant-based diets on plasma lipids. Dyslipidemia is a primary risk factor for cardiovascular disease, peripheral vascular disease, and stroke. Curren...
2. *(score=0.012812)* Plant foods and plant-based diets: protective against childhood obesity? The objective of this article is to review the epidemiologic literature examining the r...
3. *(score=0.012775)* Resolving the Coronary Artery Disease Epidemic Through Plant-Based Nutrition. The world's advanced countries have easy access to plentiful high-fat food; ironic...
4. *(score=0.012574)* Resolving the Coronary Artery Disease Epidemic Through Plant-Based Nutrition. The world's advanced countries have easy access to plentiful high-fat food; ironic...
5. *(score=0.01204)* Vegetarian diets and childhood obesity prevention. The increased prevalence of childhood overweight and obesity is not unique to industrialized societies; drama...

**Sample missed relevant docs:**

- [rel=1, found in: neither index] The spermicidal potency of Coca-Cola and Pepsi-Cola. The inhibitory effect of Old Coke, caffeine-free New Coke, New Coke, Diet Coke and Pepsi-Cola on human sper...
- [rel=1, found in: neither index] Dietary fat and semen quality among men attending a fertility clinic BACKGROUND The objective of this study was to examine the relation between dietary fats and...
- [rel=1, found in: neither index] Heavy metals in commercial fish in New Jersey. Levels of contaminants in fish are of particular interest because of the potential risk to humans who consume the...

---

### "coma"

- **Relevant docs in corpus:** 31
- **NDCG@10:** 0.0
- **FTS5 returned results:** yes
- **Missed - not in FTS nor vec top-100:** 29
- **Missed - vec top-100 only (RRF ranked too low):** 0
- **Missed - in both top-100 (fusion failed):** 1

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.012742)* Severe metabolic alkalosis in the emergency department. A case of severe metabolic alkalosis (MA) resulting from ingestion of baking soda (sodium bicarbonate) i...
2. *(score=0.01261)* A fishy cause of sudden near fatal hypotension. Seafood-borne illnesses are a common but under recognised source of morbidity. We report the case of an 80-year-...
3. *(score=0.012482)* Traumatic brain injuries in illustrated literature: experience from a series of over 700 head injuries in the Asterix comic books. BACKGROUND: The goal of the p...
4. *(score=0.012358)* Cretinism revisited. Endemic cretinism includes two syndromes: a more common neurological disorder with brain damage, deaf mutism, squint and spastic paresis of...
5. *(score=0.012238)* Hospital Admissions for Traumatic Brain Injuries, 2004: Statistical Brief #27 Excerpt This Statistical Brief presents data from the Healthcare Cost and Utilizat...

**Sample missed relevant docs:**

- [rel=1, found in: neither index] Cross-analysis of dietary prescriptions and adherence in 356 hypercholesterolaemic patients. BACKGROUND: One of the major issues in controlling serum cholestero...
- [rel=1, found in: neither index] Occupation and risk of lymphoma: a multicentre prospective cohort study (EPIC). OBJECTIVES: Evidence suggests that certain occupations and related exposures may...
- [rel=1, found in: neither index] Farming, growing up on a farm, and haematological cancer mortality. OBJECTIVES: Occupation as a farmer has been associated with increased risks of haematologica...

---

### "bagels"

- **Relevant docs in corpus:** 29
- **NDCG@10:** 0.0
- **FTS5 returned results:** NO - vocabulary mismatch
- **Missed - not in FTS nor vec top-100:** 28
- **Missed - vec top-100 only (RRF ranked too low):** 1
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.013115)* Flatulence--causes, relation to diet and remedies. In addition to causing embarrassment and unease, flatulence is linked to a variety of symptoms, some of which...
2. *(score=0.012983)* Flatulence--causes, relation to diet and remedies. In addition to causing embarrassment and unease, flatulence is linked to a variety of symptoms, some of which...
3. *(score=0.012855)* The development of the concept of dietary fiber in human nutrition. Fundamental studies of the laxative action of wheat bran were undertaken in the United State...
4. *(score=0.012731)* Influence of frequent and long-term bean consumption on colonic function and fermentation. The objective of this study was to determine the influence of frequen...
5. *(score=0.01261)* Bean consumption is associated with greater nutrient intake, reduced systolic blood pressure, lower body weight, and a smaller waist circumference ... BACKGROUN...

**Sample missed relevant docs:**

- [rel=1, found in: neither index] Poppy seed foods and opiate drug testing--where are we today? Seeds of the opium poppy plant are legally sold and widely consumed as food. Due to contamination ...
- [rel=1, found in: neither index] Morphine levels in urine subsequent to poppy seed consumption. Urine morphine levels after the consumption of poppy seeds were measured in two separate trials. ...
- [rel=1, found in: neither index] Non-celiac gluten sensitivity: literature review. BACKGROUND: A significant percentage of the general population report problems caused by wheat and/or gluten i...

---

### "mouth cancer"

- **Relevant docs in corpus:** 28
- **NDCG@10:** 0.0
- **FTS5 returned results:** yes
- **Missed - not in FTS nor vec top-100:** 22
- **Missed - vec top-100 only (RRF ranked too low):** 5
- **Missed - in both top-100 (fusion failed):** 1

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.012959)* Salivary acetaldehyde increase due to alcohol-containing mouthwash use: a risk factor for oral cancer. Increasing evidence suggests that acetaldehyde, the first...
2. *(score=0.012542)* Is oral sex really a dangerous carcinogen? Let's take a closer look. INTRODUCTION: Questions have recently arisen in the popular press about the association bet...
3. *(score=0.012414)* Diet and prevention of oral cancer: strategies for clinical practice. BACKGROUND: Oral health care professionals can play an important role in preventing oral c...
4. *(score=0.01229)* Oral sex, cancer and death: sexually transmitted cancers We briefly highlight the growing body of recent evidence linking unprotected oral sex with the developm...
5. *(score=0.01217)* Dietary factors and oral and pharyngeal cancer risk. We reviewed data from six cohort studies and approximately 40 case-control studies on the relation between ...

**Sample missed relevant docs:**

- [rel=1, found in: neither index] Diet and gallbladder cancer: a case-control study. Cancer of the gallbladder is rare but fatal, and has an unusual geographic and demographic distribution. Gall...
- [rel=1, found in: neither index] New metrics of affordable nutrition: which vegetables provide most nutrients for least cost? Measuring food prices per gram, rather than per calorie, is one way...
- [rel=1, found in: neither index] Sweet potato: a review of its past, present, and future role in human nutrition. The overall objective of this chapter is to review the past, present, and futur...

---

### "hormonal dysfunction"

- **Relevant docs in corpus:** 26
- **NDCG@10:** 0.0
- **FTS5 returned results:** NO - vocabulary mismatch
- **Missed - not in FTS nor vec top-100:** 20
- **Missed - vec top-100 only (RRF ranked too low):** 6
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.013115)* DHEA therapy in postmenopausal women: the need to move forward beyond the lack of evidence. The marked age-related decline in serum dehydroepiandrosterone (DHEA...
2. *(score=0.012983)* DHEA, DHEAS and PCOS. Approximately 20-30% of PCOS women demonstrate excess adrenal precursor androgen (APA) production, primarily using DHEAS as a marker of AP...
3. *(score=0.012855)* Dysmenorrhea. Dysmenorrhea is the leading cause of recurrent short-term school absence in adolescent girls and a common problem in women of reproductive age. Ri...
4. *(score=0.012731)* Diet and sex-hormone binding globulin, dysmenorrhea, and premenstrual symptoms. OBJECTIVE: To test the hypothesis that a low-fat, vegetarian diet reduces dysmen...
5. *(score=0.01261)* Psychological and neuroendocrinological effects of odor of saffron (Crocus sativus). AIM: The purpose of this study was to clarify the effects of saffron odor o...

**Sample missed relevant docs:**

- [rel=1, found in: neither index] The Prevalence of Phosphorus Containing Food Additives in Top Selling Foods in Grocery Stores Objective To determine the prevalence of phosphorus-containing foo...
- [rel=1, found in: neither index] Effects of Polyphosphate Additives on Campylobacter Survival in Processed Chicken Exudates Campylobacter spp. are responsible for a large number of the bacteria...
- [rel=1, found in: neither index] Prevalence and public health significance of aluminum residues in milk and some dairy products. Sixty random samples of bulk farm milk, market milk, locally man...

---

### "Barriers to Heart Disease Prevention"

- **Relevant docs in corpus:** 25
- **NDCG@10:** 0.0
- **FTS5 returned results:** NO - vocabulary mismatch
- **Missed - not in FTS nor vec top-100:** 19
- **Missed - vec top-100 only (RRF ranked too low):** 6
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.013115)* Can noncommunicable diseases be prevented? Lessons from studies of populations and individuals. Noncommunicable diseases (NCDs)--mainly cancers, cardiovascular ...
2. *(score=0.012983)* Healthy lifestyle factors in the primary prevention of coronary heart disease among men: benefits among users and nonusers of lipid-lowering and an... BACKGROUN...
3. *(score=0.012855)* Are preventive drugs preventive enough? A study of patients' expectation of benefit from preventive drugs. OBJECTIVES: The study aimed to find the threshold of ...
4. *(score=0.012731)* Effect of potentially modifiable risk factors associated with myocardial infarction in 52 countries (the INTERHEART study): case-control study. BACKGROUND: Alth...
5. *(score=0.01261)* Reductions in Cardiovascular Disease Projected from Modest Reductions in Dietary Salt Background The US diet is high in salt, with the majority coming from proc...

**Sample missed relevant docs:**

- [rel=2, found in: neither index] Effect of a very-high-fiber vegetable, fruit, and nut diet on serum lipids and colonic function. We tested the effects of feeding a diet very high in fiber from...
- [rel=2, found in: neither index] Medical nutrition therapy for hypercholesterolemia positively affects patient satisfaction and quality of life outcomes. Following a heart-healthy diet to lower...
- [rel=2, found in: vec top-100] A global survey of physicians' perceptions on cholesterol management: the From The Heart study. AIMS: Guidelines for cardiovascular disease (CVD) prevention cit...

---

### "bioavailability"

- **Relevant docs in corpus:** 21
- **NDCG@10:** 0.0
- **FTS5 returned results:** yes
- **Missed - not in FTS nor vec top-100:** 20
- **Missed - vec top-100 only (RRF ranked too low):** 0
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.012983)* Aluminum bioavailability from basic sodium aluminum phosphate, an approved food additive emulsifying agent, incorporated in cheese Oral aluminum (Al) bioavailab...
2. *(score=0.01229)* Physical activity increases the bioavailability of flavanones after dietary aronia-citrus juice intake in triathletes. Control and triathlete volunteers (n=8 an...
3. *(score=0.011898)* Bioavailability of oxalic acid from spinach, sugar beet fibre and a solution of sodium oxalate consumed by female volunteers. Oxalate bioavailability from sugar...
4. *(score=0.011801)* Vitamin B12 sources and bioavailability. The usual dietary sources of vitamin B(12) are animal foods, meat, milk, egg, fish, and shellfish. As the intrinsic fac...
5. *(score=0.011354)* Bioavailability and kinetics of sulforaphane in humans after consumption of cooked versus raw broccoli. The aim of this study was to determine the bioavailabili...

**Sample missed relevant docs:**

- [rel=1, found in: neither index] Gastro-intestinal availability of aluminium from tea. The in vitro speciation of aluminium (Al) in black tea infusion (pH 4.8) was assessed using 3000, 10,000 a...
- [rel=1, found in: neither index] Neurotoxic effects of aluminium among foundry workers and Alzheimer's disease. BACKGROUND: In a cross-sectional case-control study conducted in northern Italy, ...
- [rel=1, found in: neither index] Aluminum involvement in the progression of Alzheimer's disease. The neuroanatomic specificity with which Alzheimer's disease (AD) progresses could provide clues...

---

### "More Than an Apple a Day: Combating Common Diseases"

- **Relevant docs in corpus:** 21
- **NDCG@10:** 0.0
- **FTS5 returned results:** NO - vocabulary mismatch
- **Missed - not in FTS nor vec top-100:** 21
- **Missed - vec top-100 only (RRF ranked too low):** 0
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.013115)* Anti-cancer properties of phenolics from apple waste on colon carcinogenesis in vitro. Colorectal cancer is one of the most common cancers in Western countries....
2. *(score=0.012983)* Intake of whole apples or clear apple juice has contrasting effects on plasma lipids in healthy volunteers. PURPOSE: Fruit consumption is associated with a decr...
3. *(score=0.012855)* Cancer chemopreventive potential of apples, apple juice, and apple components. Apples ( MALUS sp., Rosaceae) are a rich source of nutrient as well as non-nutrie...
4. *(score=0.012731)* Daily apple versus dried plum: impact on cardiovascular disease risk factors in postmenopausal women. BACKGROUND: Evidence suggests that consumption of apple or...
5. *(score=0.01261)* Fruit and vegetable intake and risk of acute coronary syndrome. Prospective epidemiological studies have reported that a higher fruit and vegetable intake is as...

**Sample missed relevant docs:**

- [rel=1, found in: neither index] Characterization of bacteria, clostridia and Bacteroides in faeces of vegetarians using qPCR and PCR-DGGE fingerprinting. BACKGROUND/AIMS: This study aimed to i...
- [rel=1, found in: neither index] Endocrine-disrupting chemicals and obesity development in humans: a review. This study reviewed the literature on the relations between exposure to chemicals wi...
- [rel=1, found in: neither index] Effects of a high-fat meal on pulmonary function in healthy subjects. Obesity has important health consequences, including elevating risk for heart disease, dia...

---

### "flax oil"

- **Relevant docs in corpus:** 18
- **NDCG@10:** 0.0
- **FTS5 returned results:** yes
- **Missed - not in FTS nor vec top-100:** 12
- **Missed - vec top-100 only (RRF ranked too low):** 6
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.012884)* Flaxseed - a miraculous defense against some critical maladies. Presence of omega-3, omega-6 rich oil, alpha-linoleic acid, dietary fibers, secoisolariciresinol...
2. *(score=0.012752)* Flaxseed: a potential source of food, feed and fiber. Flaxseed is one of the most important oilseed crops for industrial as well as food, feed, and fiber purpos...
3. *(score=0.012624)* Supplementation of flaxseed oil diminishes skin sensitivity and improves skin barrier function and condition. BACKGROUND: Skin sensitivity is a common problem i...
4. *(score=0.0125)* An open-label study on the effect of flax seed powder (Linum usitatissimum) supplementation in the management of diabetes mellitus. Diabetes mellitus is charact...
5. *(score=0.012414)* Dietary milled flaxseed and flaxseed oil improve N-3 fatty acid status and do not affect glycemic control in individuals with well-controlled type ... OBJECTIVE...

**Sample missed relevant docs:**

- [rel=1, found in: neither index] Coconut oil predicts a beneficial lipid profile in pre-menopausal women in the Philippines Coconut oil is a common edible oil in many countries, and there is mi...
- [rel=1, found in: neither index] Effects of dietary coconut oil on the biochemical and anthropometric profiles of women presenting abdominal obesity. The effects of dietary supplementation with...
- [rel=1, found in: vec top-100] Effects of dietary coconut oil, butter and safflower oil on plasma lipids, lipoproteins and lathosterol levels. OBJECTIVE: The aim of this present study was to ...

---

### "Yale"

- **Relevant docs in corpus:** 18
- **NDCG@10:** 0.0
- **FTS5 returned results:** NO - vocabulary mismatch
- **Missed - not in FTS nor vec top-100:** 18
- **Missed - vec top-100 only (RRF ranked too low):** 0
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.013115)* The counseling practices of internists. OBJECTIVES: To determine the counseling practices of a group of internists in the areas of smoking, exercise, and alcoho...
2. *(score=0.012983)* Selection of levels of prevention. This article outlines the advantages and disadvantages of universal and targeted intervention programs. Two advantages of uni...
3. *(score=0.012855)* US medical researchers, the Nuremberg Doctors Trial, and the Nuremberg Code. A review of findings of the Advisory Committee on Human Radiation Expe... The Advis...
4. *(score=0.012731)* Conflicts of interest in psychiatry: strategies to cultivate literacy in daily practice. The relationship between psychiatry and pharmaceutical companies has co...
5. *(score=0.01261)* Resident duty-hour restrictions-who are we protecting?: AOA critical issues. As advocated by Nasca, our teaching programs must nurture professionalism and the e...

**Sample missed relevant docs:**

- [rel=1, found in: neither index] Facing the facelessness of public health: what's the public got to do with it? Despite compelling statistics that show we could eliminate 80%of all heart diseas...
- [rel=1, found in: neither index] Egg yolk consumption and carotid plaque. BACKGROUND: Increasingly the potential harm from high cholesterol intake, and specifically from egg yolks, is considere...
- [rel=1, found in: neither index] Dose-response efficacy of a proprietary probiotic formula of Lactobacillus acidophilus CL1285 and Lactobacillus casei LBC80R for antibiotic-associa... OBJECTIVE...

---

### "Fosamax"

- **Relevant docs in corpus:** 17
- **NDCG@10:** 0.0
- **FTS5 returned results:** NO - vocabulary mismatch
- **Missed - not in FTS nor vec top-100:** 17
- **Missed - vec top-100 only (RRF ranked too low):** 0
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.013115)* Brown adipose tissue, whole-body energy expenditure, and thermogenesis in healthy adult men. Brown adipose tissue (BAT) can be identified by (18)F-fluorodeoxygl...
2. *(score=0.012983)* Pilot evaluation of flaxseed for the management of hot flashes. The objective of this study was to evaluate, in a phase 2 pilot study, tolerability and the effe...
3. *(score=0.012855)* Glyphosate herbicide formulation: a potentially lethal ingestion. Glyphosate surfactant herbicide (GlySH) toxicity is an uncommon poisoning. We report two fatal...
4. *(score=0.012731)* TOXICITY AND CARCINOGENICITY STUDIES OF 4-METHYLIMIDAZOLE IN F344/N RATS AND B6C3F1 MICE 4-Methylimidazole (4MI) is used in the manufacture of pharmaceuticals, ...
5. *(score=0.01261)* Flaxseed fed pork: n-3 fatty acid enrichment and contribution to dietary recommendations. The potential to increase n-3 fatty acid (FA) intake via flaxseed fed ...

**Sample missed relevant docs:**

- [rel=1, found in: neither index] The role of phytic acid in legumes: antinutrient or beneficial function? This review describes the present state of knowledge about phytic acid (phytate), which...
- [rel=1, found in: neither index] Inositol Hexakisphosphate Inhibits Osteoclastogenesis on RAW 264.7 Cells and Human Primary Osteoclasts Background Inoxitol hexakisphosphate (IP6) has been found...
- [rel=1, found in: neither index] Bisphosphonate-associated osteonecrosis of the jaw: report of a task force of the American Society for Bone and Mineral Research. ONJ has been increasingly susp...

---

### "Benefits of Fenugreek Seeds"

- **Relevant docs in corpus:** 17
- **NDCG@10:** 0.0
- **FTS5 returned results:** NO - vocabulary mismatch
- **Missed - not in FTS nor vec top-100:** 16
- **Missed - vec top-100 only (RRF ranked too low):** 1
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.013115)* Xenohormesis: health benefits from an eon of plant stress response evolution Xenohormesis is a biological principle that explains how environmentally stressed p...
2. *(score=0.012983)* Glucoraphanin and 4-hydroxyglucobrassicin contents in seeds of 59 cultivars of broccoli, raab, kohlrabi, radish, cauliflower, brussels sprouts, kal... The impor...
3. *(score=0.012855)* Nutritional quality and health benefits of chickpea (Cicer arietinum L.): a review. Chickpea (Cicer arietinum L.) is an important pulse crop grown and consumed ...
4. *(score=0.012731)* An open-label study on the effect of flax seed powder (Linum usitatissimum) supplementation in the management of diabetes mellitus. Diabetes mellitus is charact...
5. *(score=0.01261)* Flaxseed - a miraculous defense against some critical maladies. Presence of omega-3, omega-6 rich oil, alpha-linoleic acid, dietary fibers, secoisolariciresinol...

**Sample missed relevant docs:**

- [rel=1, found in: vec top-100] Cinnamon intake lowers fasting blood glucose: meta-analysis. Cinnamon, the dry bark and twig of Cinnamomum spp., is a rich botanical source of polyphenolics tha...
- [rel=1, found in: neither index] Effects of a low-fat, high-fiber diet and exercise program on breast cancer risk factors in vivo and tumor cell growth and apoptosis in vitro. The present study...
- [rel=1, found in: neither index] Intensive lifestyle changes may affect the progression of prostate cancer. PURPOSE: Men with prostate cancer are often advised to make changes in diet and lifes...

---

### "weight gain"

- **Relevant docs in corpus:** 15
- **NDCG@10:** 0.0
- **FTS5 returned results:** yes
- **Missed - not in FTS nor vec top-100:** 15
- **Missed - vec top-100 only (RRF ranked too low):** 0
- **Missed - in both top-100 (fusion failed):** 0

**Top-5 retrieved by RRF (all irrelevant):**

1. *(score=0.012884)* Increased food energy supply is more than sufficient to explain the US epidemic of obesity. BACKGROUND: The major drivers of the obesity epidemic are much debat...
2. *(score=0.012855)* Weight gain over 5 years in 21,966 meat-eating, fish-eating, vegetarian, and vegan men and women in EPIC-Oxford. BACKGROUND: Cross-sectional studies have shown ...
3. *(score=0.01268)* Meat consumption and prospective weight change in participants of the EPIC-PANACEA study. BACKGROUND: Meat intake may be related to weight gain because of its h...
4. *(score=0.012053)* Energy Balance and Obesity This paper describes the interplay among energy intake, energy expenditure and body energy stores and illustrates how an understandin...
5. *(score=0.011811)* Intake of total, animal and plant protein and subsequent changes in weight or waist circumference in European men and women: the Diogenes project. BACKGROUND: A...

**Sample missed relevant docs:**

- [rel=1, found in: neither index] Flaxseed supplementation improved insulin resistance in obese glucose intolerant people: a randomized crossover design Background Obesity leads to an increase i...
- [rel=1, found in: neither index] An open-label study on the effect of flax seed powder (Linum usitatissimum) supplementation in the management of diabetes mellitus. Diabetes mellitus is charact...
- [rel=1, found in: neither index] The Efficacy of Paroxetine and Placebo in Treating Anxiety and Depression: A Meta-Analysis of Change on the Hamilton Rating Scales Background Previous meta-anal...

---
