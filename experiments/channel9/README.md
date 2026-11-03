\# Channel 9 Satellite Telemetry Anomaly Detection Experiment



\## 1. Purpose



This experiment investigates whether temporal and drift-related feature engineering improves satellite telemetry anomaly detection.



It also investigates a confidence-based adaptive routing strategy in which a lightweight model screens telemetry observations and a stronger model is invoked for selected uncertain observations.



The experiment uses ESA Anomaly Detection Benchmark (ESA-ADB), Mission 2, channel 9.



The work compares three Random Forest feature configurations and evaluates an experimental adaptive detection strategy.



\## 2. Dataset



\- Dataset: ESA Anomaly Detection Benchmark (ESA-ADB)

\- Mission: Mission 2

\- Telemetry channel: channel\_9

\- Total observations: 7,387,262

\- Anomalous observations: 166,621

\- Anomaly proportion: approximately 2.26%

\- Timestamp range: 2000–2003



The dataset contains irregularly spaced timestamps. Rolling features are therefore calculated using observation-count windows rather than fixed-duration time windows.



\## 3. Feature Engineering



\### 3.1 Baseline: 7 features



The baseline feature set contains:



1\. Current value

2\. Difference

3\. Absolute difference

4\. Rolling mean (30 observations)

5\. Rolling standard deviation (30 observations)

6\. Rolling mean (120 observations)

7\. Rolling standard deviation (120 observations)



\### 3.2 Temporal model: 10 features



The temporal model adds:



8\. Deviation over 30 observations

9\. Deviation over 120 observations

10\. Variability ratio



These features help represent deviations from recent behaviour and changes in local variability.



\### 3.3 Drift model: 13 features



The drift model adds three further features to the 10-feature configuration:



11\. Long-term slope

12\. Short-long mean gap

13\. Cumulative deviation



These features are intended to represent longer-term trends and persistent deviations.



All engineered features use past observations rather than future observations to avoid look-ahead leakage.



\## 4. Experimental Setup



\### 4.1 Chronological data split



The dataset is divided chronologically:



| Split | Percentage | Observations |

|---|---:|---:|

| Training period | 70% | 5,171,083 |

| Validation | 15% | 1,108,089 |

| Testing | 15% | 1,108,090 |



The validation and test periods are kept separate.



\### 4.2 Model configuration



The saved Random Forest models were trained in the earlier Colab experiment.



The matched model experiments used:

\- Training sample: 100,000 observations

\- Number of trees: 60

\- Random state: 42



The local evaluation scripts load these saved models. They do not retrain them.



\### 4.3 Threshold selection



Decision thresholds are selected using validation data only.



The threshold-selection procedure maximises F1 subject to a maximum false-positive rate of 0.01.



The selected thresholds are:



| Model | Validation threshold |

|---|---:|

| 7-feature | 0.95622046 |

| 10-feature | 0.94915256 |

| 13-feature | 0.94787797 |



The selected thresholds are then applied to the held-out test data.



Predictions are processed in batches of 100,000 observations.



\## 5. Three-Model Test Results



| Metric | 7 features | 10 features | 13 features |

|---|---:|---:|---:|

| Precision | 0.7987 | 0.8122 | \*\*0.8204\*\* |

| Recall | 0.2242 | 0.2241 | \*\*0.2266\*\* |

| F1-score | 0.3501 | 0.3512 | \*\*0.3552\*\* |

| PR-AUC | 0.3000 | 0.3190 | \*\*0.3337\*\* |

| False-positive rate | 0.001653 | 0.001516 | \*\*0.001452\*\* |



\### Interpretation



The 10-feature model improves PR-AUC and F1 compared with the 7-feature baseline.



The 13-feature model achieves the best results among the three configurations.



Compared with the 7-feature baseline, the 13-feature model achieves:

\- An increase in precision from approximately 79.87% to 82.04%.

\- An increase in recall from approximately 22.42% to 22.66%.

\- An increase in F1 from approximately 0.3501 to 0.3552.

\- An increase in PR-AUC from approximately 0.3000 to 0.3337.



Recall remains low, indicating that many anomalous observations are still missed.



\## 6. Confusion Matrices



\### 6.1 Baseline: 7 features



| | Predicted normal | Predicted anomaly |

|---|---:|---:|

| Actual normal | 1,074,812 | 1,780 |

| Actual anomaly | 24,436 | 7,062 |



\### 6.2 Temporal model: 10 features



| | Predicted normal | Predicted anomaly |

|---|---:|---:|

| Actual normal | 1,074,960 | 1,632 |

| Actual anomaly | 24,440 | 7,058 |



\### 6.3 Drift model: 13 features



| | Predicted normal | Predicted anomaly |

|---|---:|---:|

| Actual normal | 1,075,029 | 1,563 |

| Actual anomaly | 24,359 | 7,139 |



\## 7. Confidence-Based Adaptive Routing Experiment



\### 7.1 Objective



The adaptive experiment investigates whether a lightweight model can screen most telemetry observations while invoking a stronger model only when the baseline prediction is close to its decision threshold.



The 7-feature model is used as the initial screening model. The 13-feature model is used as the stronger model.



\### 7.2 Routing rule



The baseline model calculates an anomaly probability for each observation.



An observation is escalated when its probability is within a selected margin of the 7-feature validation threshold.



The stronger model's prediction replaces the baseline prediction for escalated observations.



The 10-feature model remains part of the feature comparison and is not used in this routing experiment.



\### 7.3 Validation experiment



Five margins were evaluated using validation data:



| Margin | Escalation rate | Precision | Recall | F1 |

|---|---:|---:|---:|---:|

| ±0.005 | 0.055% | 0.7335 | 0.4191 | 0.5334 |

| ±0.010 | 0.127% | 0.7430 | 0.4195 | 0.5363 |

| ±0.020 | 0.257% | 0.7482 | 0.4188 | 0.5370 |

| ±0.050 | 1.325% | 0.7568 | 0.4202 | 0.5404 |

| ±0.100 | 1.518% | 0.7556 | 0.4219 | 0.5415 |



The ±0.100 margin was selected because it achieved the highest F1 among the tested hybrid configurations on validation data.



\### 7.4 Held-out test results



The selected policy was evaluated on the separate test period without further tuning.



| Metric | 7-feature baseline | 13-feature model always | Adaptive hybrid |

|---|---:|---:|---:|

| Precision | 0.7987 | \*\*0.8204\*\* | 0.8200 |

| Recall | 0.2242 | \*\*0.2266\*\* | 0.2244 |

| F1-score | 0.3501 | \*\*0.3552\*\* | 0.3524 |

| False-positive rate | 0.001653 | 0.001452 | \*\*0.001442\*\* |

| False positives | 1,780 | 1,563 | \*\*1,552\*\* |

| False negatives | 24,436 | \*\*24,359\*\* | 24,430 |



The adaptive strategy escalated 10,633 observations, representing approximately 0.96% of the test observations.



\### 7.5 Runtime measurement



Measured inference times in one local run:



| Model | Runtime |

|---|---:|

| 7-feature baseline | 0.740 seconds |

| 13-feature model always | 0.990 seconds |

| Adaptive hybrid | 1.172 seconds |



The adaptive implementation was slower in this measured run, despite invoking the stronger model for fewer than 1% of observations.



Routing and data-selection overhead can outweigh the cost of the additional model predictions.



Therefore, this experiment does not establish a runtime or resource-efficiency improvement.



\### 7.6 Interpretation



The adaptive hybrid achieves slightly higher precision and fewer false positives than the baseline.



However, it does not outperform the always-on 13-feature model in F1 or recall.



The experiment demonstrates that confidence-based escalation can alter detection behaviour while invoking the stronger model selectively. Its resource-efficiency benefit remains unproven.



\## 8. How to Run



Run the commands from the repository root with the experiment dependencies installed.



\### Evaluate the three feature configurations



```cmd

python experiments\\channel9\\evaluate\_models.py

```



\### Generate comparison charts



```cmd

python experiments\\channel9\\plot\_comparison.py

```



\### Analyse baseline confidence



```cmd

python experiments\\channel9\\analyze\_confidence.py

```



\### Evaluate adaptive routing on validation data



```cmd

python experiments\\channel9\\test\_adaptive\_routing.py

```



\### Run the final adaptive test evaluation



```cmd

python experiments\\channel9\\final\_adaptive\_test.py

```



The final adaptive test script uses the routing margin selected on validation data. Do not tune the margin using test results.



\## 9. Output Files



Generated experiment outputs are stored in `results/channel9/`.



\### Model comparison



\- `three\_model\_comparison.json`

\- `three\_model\_metric\_comparison.png`

\- `three\_model\_confusion\_matrices.png`

\- `three\_model\_improvement\_summary.png`



\### Earlier comparison outputs



\- `model\_comparison.json`

\- `metric\_comparison.png`

\- `confusion\_matrices.png`



\### Adaptive routing outputs



\- `confidence\_analysis.csv`

\- `adaptive\_routing\_validation.csv`

\- `final\_adaptive\_test\_results.json`



\## 10. Experiment Code Files



The experiment scripts are stored in `experiments/channel9/`.



\- `evaluate\_models.py`: loads saved models, selects validation thresholds and evaluates test performance.

\- `plot\_comparison.py`: generates feature-model comparison charts.

\- `analyze\_confidence.py`: examines baseline prediction probabilities and candidate escalation rates.

\- `test\_adaptive\_routing.py`: compares adaptive routing margins using validation data.

\- `final\_adaptive\_test.py`: evaluates the locked adaptive routing policy on held-out test data.

\- `requirements-experiment.txt`: records the Python package versions used for the local model experiment.



\## 11. Limitations



The current experiments have the following limitations:



1\. Only one telemetry channel from Mission 2 has been evaluated.

2\. Recall remains low across all model configurations.

3\. The 13-feature model improves overall test metrics, but the absolute F1 improvement is modest.

4\. The adaptive routing strategy does not outperform the always-on 13-feature model in F1 or recall.

5\. The measured adaptive inference runtime is slower than both individual model runs in the recorded experiment.

6\. Runtime measurements are from one local run and may vary with hardware, system load and execution conditions.

7\. The experiments do not establish general performance across all satellite missions or channels.

8\. The adaptive strategy uses proximity to a probability threshold as an uncertainty proxy. It is not a calibrated measure of model uncertainty.

9\. Impact-aware prioritisation, sensor reliability modelling, cross-channel incident correlation and counterfactual response planning have not yet been implemented or validated.



\## 12. Future Work



Further research may investigate:



\- Improving anomaly recall.

\- Evaluating additional telemetry channels and missions.

\- Calibrating model confidence.

\- Developing a routing policy that reduces measured computational cost.

\- Investigating sensor reliability.

\- Modelling temporal relationships between channels.

\- Developing impact-aware anomaly prioritisation.

\- Exploring counterfactual incident response strategies.



\## 13. Conclusion



The feature-engineering experiments show that adding temporal and drift-related information improves anomaly detection performance on the selected Mission 2 channel 9 test dataset.



The 13-feature Random Forest achieves the best overall F1 and PR-AUC among the three feature configurations.



The adaptive routing experiment demonstrates selective escalation and a reduction in false positives compared with the baseline, but it does not establish a runtime improvement or outperform the 13-feature model in F1.



These findings are limited to the evaluated dataset and should not be generalised to all satellite missions without further experiments.

