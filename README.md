# Pátrač 2 Service

Umožňuje spustit omezenou sadu funkcí systému Pátrač přes API.

## Data
Pro běh vyžaduje data ve stejné struktuře jako má Pátrač. 
Postupně se toto bude optimalizovat, ale v této chvíli je to plný rozsah pro celý kraj.

## Stav
Aktuálně se jedná o první implementaci ve stavu PoC, tedy nejsou jistě vyladěny všechny 
možné stavy a error 500 asi nebude neobvyklý.

## Build

```bash
docker build -t ruz76-patrac2-service .
```

## Spuštění
Spouští se v módu pro vývoj, tedy by měl být po spuštění vidět zápis výpočtů.

```bash
docker run -v /data/patracdata:/data/patracdata -p 5000:5000 -it ruz76-patrac2-service
```

