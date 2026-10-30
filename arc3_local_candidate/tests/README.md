# Testy lokalne

Uruchom z katalogu głównego repozytorium:

```bash
python -m unittest discover -s arc3_local_candidate/tests -t . -v
```

Testy korzystają wyłącznie z biblioteki standardowej Pythona. Nie inicjują Kaggle API, GPU, sieci, gatewaya ani gry.