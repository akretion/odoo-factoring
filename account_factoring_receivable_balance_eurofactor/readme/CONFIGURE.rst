- use a company with l10n_fr
- alternatively you may create a new one with

Here you can create a new company with EUROFACTOR settings for default currency


.. code-block:: python

   env["res.company"]._create_french_company(company_name="my new company")


Here you may create settings for a new installed currency

.. code-block:: python

   env.browse(mycompany_id)._configure_eurof_factoring()


- now you can go to journals and filter them with `Factor type`.
