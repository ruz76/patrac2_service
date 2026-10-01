# Pátrač 2 Service

Umožňuje spustit omezenou sadu funkcí systému Pátrač přes API.

Existují dvě verze:
* Nativní pro Windows 10
* [docker](https://github.com/ruz76/patrac2_service/tree/docker_version)

Popis nativní verze je v [service/README.md](./service/README.md)

## Rozhraní
Popis rozhraní je k dispozici v [rozhraní](./api_doc/service.yaml)

## Konfigurace
Popis konfigurace je k dispozici na [patrac.czu.cz](https://patrac.czu.cz/cache/article-data/P%C3%A1tra%C4%8D/patrac2_vysledky/3_SW_liniove_patrani.pdf)

## Data
Pro běh vyžaduje data ve stejné struktuře jako má Pátrač. 

## Build

```bash
docker build -t ruz76-patrac2-service .
```

## Spuštění
Spouští se v módu pro vývoj, tedy by měl být po spuštění vidět zápis výpočtů.

```bash
docker run -v /data/patracdata:/data/patracdata -p 5000:5000 -it ruz76-patrac2-service
```

