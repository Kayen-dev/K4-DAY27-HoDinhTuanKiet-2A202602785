# Reflection

**Hardest faults.** Subtle magnitude changes in order volume, amount distribution,
feature skew, and embedding drift were hardest. Their measurements can remain
inside the published clean-stream bounds, so a single threshold can miss a real
fault. Narrowing the row-count and amount bands from three to 2.5 standard
deviations improved public detection, but introduced occasional false alarms.
Lineage also required care: the event envelope lists the triggering order input,
while the actual staging graph must include both orders and customers. Comparing
only the envelope with the graph would misclassify clean runs.

**Cost versus coverage.** I used one metered check per event. This covered all
five event types and stayed within the private budget, so skipping checks would
mainly sacrifice recall. With another pass, I would calibrate per-metric alert
thresholds on more labeled clean and faulty streams, and use an online robust
estimate for borderline values. I would require stronger evidence for near-bound
alerts to limit false positives. The private result (32.2 points, 64.81% recall,
0.68% false-positive rate) shows that the current conservative rules still miss
many subtle faults.
