# vmt-plan: Turbonomic API plan engine

*vmt-plan* is a companion library to [vmt-connect](https://github.com/turbonomic/vmt-connect)
for working with the Turbonomic API. The core purpose of the library is to provide
interfaces for constructing and running plans within Turbonomic.


## Installation

```bash
pip install vmtplan
```


## Usage

```python
# Basic Plan - Note the import is vmtplanner <!>
import vmtconnect as vc
import vmtplanner as vp

vmt = vc.Session(host='localhost', username='bob', password='*****')

# scoping to two groups by UUID
scope = ['430e28cbaabf35522a180859d4160562d123ac78',
        'e48fd3270917221d3e6290e1affead34b872e95b']
scenario = vp.PlanSpec('custom scenario', scope=scope)

# add 5 copies of a VM immediately using positional arguments
scenario.change_entity(vp.EntityAction.ADD, ['1341c28a-c9b7-46a5-ab25-321260482a91'], [0], 5)

# add 1 copy each month for 2 months using named arguments
scenario.change_entity(action=vp.EntityAction.ADD,
                      targets=['1341c28a-c9b7-46a5-ab25-321260482a91'],
                      count=1,
                      projection=[30, 60])

plan = vp.Plan(vmt, scenario)
plan.run()
```

## Documentation

The [user guide](https://turbonomic.github.io/vmt-plan/userguide.html) is a
good place to start. Detailed documentation is also available [here](https://turbonomic.github.io/vmt-plan).
