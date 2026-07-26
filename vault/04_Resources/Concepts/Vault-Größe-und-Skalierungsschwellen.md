---
description: Wie groß ein Vault werden darf, bevor flache Notizstrukturen anfangen zu brechen — der Schwellenwert, ab dem Ordner, Communities oder ein Graph-Layer nötig werden.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-02-07
created: 2026-02-07
kind: concept
topics:
  - vault-architecture
  - scaling
tags:
  - domain/toolkit-meta
---

# Vault-Größe und Skalierungsschwellen

*(Vault Size and Scaling Thresholds — this note's title and body are deliberately in German with
umlauts, one of this vault's planted Unicode test cases; see [[Test-Corpus-Map]].)*

Ein Vault mit wenigen hundert Notizen funktioniert flach: ein Index, ein paar Ordner, dichte
Wikilinks — genug, damit ein Mensch oder ein Agent sich zurechtfindet, ohne dass Cluster explizit
markiert werden müssen. Über einer bestimmten Größenordnung reicht das nicht mehr: die Anzahl
möglicher Verbindungen wächst schneller als die Anzahl der Notizen, und ohne
[[Community-Detection-and-Bridge-Notes|Community-Erkennung]] wird der Graph für einen Menschen
unlesbar, lange bevor er für eine Maschine unlesbar wird.

## Warum dieser Vault absichtlich klein bleibt

Dieser Beispiel-Vault liegt bewusst unter der Schwelle, ab der eine flache Struktur anfängt zu
brechen — genug Notizen, um realistische Dichte zu zeigen, aber wenig genug, dass die drei Cluster
noch von Hand nachvollziehbar sind, nicht nur algorithmisch. Siehe [[Hardware-Inventory]] und
[[Reference-Library]] für zwei sehr konkrete, kleine Instanzen derselben Entscheidung: eine
Tabelle in einer Notiz statt ein Ordner pro Eintrag, weil die Größe die zusätzliche Struktur noch
nicht rechtfertigt.

## Related

- [[Community-Detection-and-Bridge-Notes]]
- [[Atomic-Notes]]
- [[Hardware-Inventory]]
- [[Reference-Library]]
- [[Test-Corpus-Map]]
