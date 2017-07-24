.. # [{'id': <uuid>, 'action': <add|delete|replace>, 'template': <uuid>, 'count': <int>, 'projection': [<int>]}]

Entity Specification
---------------------

The entity specification is a :class:`list` of :class:`dict` entries. Each
  entry in the list represents one entity to be added, removed, or modified
  in the plan. The format structure is as follows:

.. code:: python

  {'id': <uuid>,
   'action': PlanSetting.<add|delete|replace>,
   'template': <uuid>,
   'count': <int>,
   'projection': [<int, ...>]
  }

Examples:

.. code:: python

  entities = [
    # add 5 copies immediately, and every month for 2 months
    {'id': '1341c28a-c9b7-46a5-ab25-321260482a91',
     'action': PlanSetting.add,
     'count': 5,
     'projection': [0, 30, 60]
    },
    # replace VM with template in a month
    {'id': '1341c28a-c9b7-46a5-ab25-321260482a91',
     'action': PlanSetting.replace,
     'template': '63513223-d9a7-46b5-df98-324351482a91',
     'count': 1,
     'projection': [30]
    },
    # remove VM immediately
    {'id': '1341c28a-c9b7-46a5-ab25-321260482a91',
     'action': PlanSetting.remove,
     'count': 1,
     'projection': [0]
    }
  ]