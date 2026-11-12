import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from src import s3_analytics as s3
from src.common import OUT, INTERIM

nodes, index, A, _ = s3.load_graph(8)
labels, k, secs = s3.louvain_partition(A, resolution=1.0, seed=1)
PT = s3.transition(A).T.tocsr()
pr, _ = s3.pagerank_serial(PT)
people = {}
with open(os.path.join(INTERIM, "people.csv"), newline="", encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        people[r["nconst"]] = r["primary_name"]
path = os.path.join(OUT, "node_labels_top8.csv")
with open(path, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["nconst", "name", "community", "pagerank", "degree"])
    deg = np.asarray(A.sum(axis=1)).ravel()
    for i, nid in enumerate(nodes):
        w.writerow([nid, people.get(nid, nid), int(labels[i]), f"{pr[i]:.10f}", int(deg[i])])
print("wrote", path, "k=", k, "Q=", round(float(s3.modularity(A, labels)), 4))
