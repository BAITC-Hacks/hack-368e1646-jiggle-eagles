# Electricity fundamentals

## Quantities and units

| Concept | Operational meaning |
| --- | --- |
| Power, kW or MW | Energy transfer rate; readings may be instantaneous, averaged or maxima. |
| Energy, kWh or MWh | Amount transferred over time; readings may be interval or cumulative. |
| Installed/rated capacity | Equipment rating under specified conditions; not measured output or guaranteed availability. |
| Demand/load | Power required/drawn within a scope; check dataset definitions. |
| Peak demand | Highest demand for a stated period and measurement window. |
| Load profile | Load over time; its resolution and aggregation affect visible peaks. |

`1 MW = 1,000 kW`; `1 MWh = 1,000 kWh`; `1 kWh = 1,000 Wh`.
`kW × h = kWh`; power and energy are different dimensions. kVA and kvar are not interchangeable with kW.

`E = P × t` requires constant power or its time-average over exactly that duration. Energy integrates power over time. One instantaneous sample cannot determine interval energy; see [calculations](calculations.md).

## Scope and direction

Generation produces electricity; transmission moves bulk electricity; distribution delivers it locally; consumption uses it. Meter boundaries, losses, onsite generation and storage affect how these quantities relate.

Import/export describe boundary flows; sign conventions vary. Signed net measurements may hide separate import/export flows and do not establish gross consumption. Confirm direction/scope before aggregation or comparison.

Sources: E1, E2, N1 in [references](references.md).
