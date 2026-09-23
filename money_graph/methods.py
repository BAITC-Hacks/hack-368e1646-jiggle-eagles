"""Calculation settings shared by measurements and their saved descriptions."""
from copy import deepcopy
import math

CONFIG = {
    'rules_version': 2, 'cluster_description_version': 3,
    'community_algorithm': 'louvain', 'louvain_seed': 42, 'resolution': 1.0, 'threshold': 1e-7,
    'amount_absolute_tolerance_kzt': 0.01, 'amount_relative_tolerance': 1e-12,
    'consolidator_min': 3, 'distributor_min': 5, 'fan_ratio': 2,
    'coordinator_in': 2, 'coordinator_out': 2, 'coordinator_communities': 3,
    'transit_tolerance': 0.2, 'confidence_base': 0.55, 'confidence_gain': 0.35,
    'consolidator_scale': 10, 'distributor_scale': 20, 'coordinator_scale': 6,
    'terminal_base': 0.45, 'terminal_gain': 0.15, 'terminal_scale': 5,
    'peripheral_isolate': 0.1, 'peripheral_connected': 0.2,
    'ambiguity_deduction': 0.1, 'boundary_multiplier': 0.6, 'seed_multiplier': 0.85,
    'priority_in_weight': 0.30, 'priority_out_weight': 0.25, 'priority_cross_weight': 0.20,
    'priority_tx_weight': 0.15, 'priority_volume_weight': 0.10,
    'priority_in_scale': 10, 'priority_out_scale': 10, 'priority_cross_scale': 5, 'priority_tx_scale': 30,
}


def configuration(overrides: dict | None = None) -> dict:
    """Reject unknown/unsafe settings; callers own their copy."""
    result = deepcopy(CONFIG)
    if overrides is not None:
        if not isinstance(overrides, dict) or set(overrides) - set(result):
            raise ValueError('Unknown calculation setting')
        result.update(overrides)
    if result['community_algorithm'] not in {'louvain', 'connected_components'}:
        raise ValueError('Unsupported community method')
    for key, value in result.items():
        if key == 'community_algorithm':
            continue
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('Calculation settings must be finite nonnegative numbers')
        if isinstance(CONFIG[key], int) and type(value) is not int:
            raise ValueError('Count settings must be integers')
        if ('scale' in key or key.endswith('_min') or key in {'resolution', 'threshold', 'transit_tolerance'}) and value <= 0:
            raise ValueError('Scale and threshold settings must be positive')
    if not 0 < result['transit_tolerance'] < 1:
        raise ValueError('Transit tolerance must be between zero and one')
    if not math.isclose(sum(v for k, v in result.items() if k.startswith('priority_') and k.endswith('_weight')), 1):
        raise ValueError('Priority weights must sum to one')
    for key in ('boundary_multiplier', 'seed_multiplier', 'peripheral_isolate', 'peripheral_connected'):
        if result[key] > 1:
            raise ValueError('Confidence settings must not exceed one')
    if result['confidence_base'] + result['confidence_gain'] > 1 or result['terminal_base'] + result['terminal_gain'] > 1:
        raise ValueError('Confidence must not exceed one')
    if result['ambiguity_deduction'] > min(result['confidence_base'], result['terminal_base']):
        raise ValueError('Ambiguity deduction exceeds base confidence')
    return result


def rule_parameters(config: dict) -> dict:
    return dict(incoming=config['coordinator_in'], outgoing=config['coordinator_out'],
                communities=config['coordinator_communities'], consolidator=config['consolidator_min'],
                distributor=config['distributor_min'], ratio=config['fan_ratio'],
                lower=round(1 - config['transit_tolerance'], 6), upper=round(1 + config['transit_tolerance'], 6))


def scoring_description(c: dict) -> dict[str, str]:
    """Persist formulas with actual values; old analyses never read today's defaults."""
    return {
        'confidence': f"Base + gain × capped support; coordinator {c['confidence_base']} + {c['confidence_gain']} × min(communities/{c['coordinator_scale']}, 1); "
            f"consolidator scale {c['consolidator_scale']}; distributor scale {c['distributor_scale']}; "
            f"transit support max(0, 1 − abs(out/in − 1)/{c['transit_tolerance']}); "
            f"terminal {c['terminal_base']} + {c['terminal_gain']} × min(incoming/{c['terminal_scale']}, 1); "
            f"peripheral {c['peripheral_isolate']} isolated / {c['peripheral_connected']} connected. "
            f"Overlapping rules subtract {c['ambiguity_deduction']}; depth four ×{c['boundary_multiplier']}; seed ×{c['seed_multiplier']}. "
            'Tie order: coordinator, consolidator, distributor, transit, terminal, peripheral. Heuristic support, not probability.',
        'priority': ' + '.join(f"{c['priority_' + key + '_weight']} × min({label}/{c['priority_' + key + '_scale']}, 1)"
            for key, label in [('in', 'incoming peers'), ('out', 'outgoing peers'), ('cross', 'cross-community peers'), ('tx', 'incident transfer count')])
            + f" + {c['priority_volume_weight']} × log1p(incident KZT)/log1p(max incident KZT). Contributions rounded to six decimals; numeric gid breaks ties.",
        'community': f"{c['community_algorithm']}; undirected projection; reciprocal KZT added; self-links excluded; isolates retained. "
            + (f"Seed {c['louvain_seed']}; resolution {c['resolution']}; threshold {c['threshold']}." if c['community_algorithm'] == 'louvain' else 'Connected components; no resolution or random seed used.'),
    }
