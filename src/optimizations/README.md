# Optimizations

## Install vectorlite SQLite extension:

1. `pip install vectorlite-py`

2. Locate .so file:
```
python
>>> import vectorlite_py
>>> vectorlite_py.vectorlite_path()
'/Users/ferdi/miniconda3/envs/aco/lib/python3.13/site-packages/vectorlite_py/vectorlite'
```

3. Load into sqlite DB

```
sqlite3 ~/.cache/agent-copilot/db/experiments.sqlite
sqlite> .load /Users/ferdi/miniconda3/envs/aco/lib/python3.13/site-packages/vectorlite_py/vectorlite
```

## Using vectorlite's SQL UDFs

 - INSERT vectors with `vector_from_json`: `INSERT INTO my_table(rowid, embedding_column) VALUES (0, vector_from_json('[1,2,3]'));`
 - Calculate l2(squared) distanceswith `vector_distance`: `SELECT vector_distance(vector_from_json('[1,2,3]'), vector_from_json('[3,4,5]'), 'l2');`
 - Get 2 most similar entries from DB with `knn_search`: `SELECT rowid, distance FROM my_table WHERE knn_search(embedding_column, knn_param(vector_from_json('[3,4,5]'), 2));`
