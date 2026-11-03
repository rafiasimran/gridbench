# GridBench

A clean, documented, research-ready dataset of Germany's electricity grid from January 2020 to October 2026, with a small Python toolkit to load it.

## The problem

Anyone who studies the German grid starts by downloading the same public data and cleaning it again: clock changes, missing hours, prices that switched from hourly to 15-minute values, units that differ between series. It takes weeks, and small differences in how each team cleans the data make results hard to compare.

## What GridBench will give

- Hourly data for 2020 to 2026: electricity demand, generation by source and day-ahead prices, in UTC with units in every column name
- A data quality report that lists every gap, duplicate and fix
- A Python loader: one call to get any period and any columns
- Releases you can cite

## Status

In progress. Built in small steps; see the commit history.

## Data

Source: Bundesnetzagentur | SMARD.de, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The code in this repository is MIT licensed.
