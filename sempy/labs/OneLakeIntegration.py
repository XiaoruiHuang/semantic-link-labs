import sempy
import sempy.fabric as fabric
import pandas as pd

def export_model_to_onelake(dataset: str, workspace: str | None = None, destination_lakehouse: str | None = None, destination_workspace: str | None = None):

    """
    
    Documentation is available here: https://github.com/microsoft/semantic-link-labs?tab=readme-ov-file#export_model_to_onelake

    """

    if workspace == None:
        workspace_id = fabric.get_workspace_id()
        workspace = fabric.resolve_workspace_name(workspace_id)
    else:
        workspace_id = fabric.resolve_workspace_id(workspace)

    if destination_workspace == None:
        destination_workspace = workspace
        destination_workspace_id = workspace_id
    else:
        destination_workspace_id = fabric.resolve_workspace_id(destination_workspace)

    dfD = fabric.list_datasets(workspace = workspace)
    dfD_filt = dfD[dfD['Dataset Name'] == dataset]

    if len(dfD_filt) == 0:
        print(f"The '{dataset}' semantic model does not exist in the '{workspace}' workspace.")
        return

    tmsl = f"""
    {{
    'export': {{
    'layout': 'delta',
    'type': 'full',  
    'objects': [  
        {{  
        'database': '{dataset}'
        }}  
    ]  
    }}  
    }}
    """

    # Export model's tables as delta tables
    try:
        fabric.execute_tmsl(script = tmsl, workspace = workspace)
        print(f"The '{dataset}' semantic model's tables have been exported as delta tables to the '{workspace}' workspace.\n")
    except:
        print(f"ERROR: The '{dataset}' semantic model's tables have not been exported as delta tables to the '{workspace}' workspace.")
        print(f"Make sure you enable OneLake integration for the '{dataset}' semantic model. Follow the instructions here: https://learn.microsoft.com/power-bi/enterprise/onelake-integration-overview#enable-onelake-integration")
        return
    
    # Create shortcuts if destination lakehouse is specified
    if destination_lakehouse is not None:
        # Destination...
        dfI_Dest = fabric.list_items(workspace = destination_workspace)
        dfI_filt = dfI_Dest[(dfI_Dest['Type'] == 'Lakehouse') & (dfI_Dest['Display Name'] == destination_lakehouse)]

        if len(dfI_filt) == 0:
            print(f"The '{destination_lakehouse}' lakehouse does not exist within the '{destination_workspace}' workspace.")
            # Create lakehouse
            destination_lakehouse_id = fabric.create_lakehouse(display_name = destination_lakehouse, workspace = destination_workspace)
            print(f"The '{destination_lakehouse}' lakehouse has been created within the '{destination_workspace}' workspace.\n")        
        else:
            destination_lakehouse_id = dfI_filt['Id'].iloc[0]

        # Source...
        dfI_Source = fabric.list_items(workspace = workspace)
        dfI_filtSource = dfI_Source[(dfI_Source['Type'] == 'SemanticModel') & (dfI_Source['Display Name'] == dataset)]
        sourceLakehouseId = dfI_filtSource['Id'].iloc[0]

        # Valid tables
        dfP = fabric.list_partitions(dataset = dataset, workspace = workspace, additional_xmla_properties=['Parent.SystemManaged'])
        dfP_filt = dfP[(dfP['Mode'] == 'Import') & (dfP['Source Type'] != 'CalculationGroup') & (dfP['Parent System Managed'] == False)]
        dfC = fabric.list_columns(dataset = dataset, workspace = workspace)
        tmc = pd.DataFrame(dfP.groupby('Table Name')['Mode'].nunique()).reset_index()
        oneMode = tmc[tmc['Mode'] == 1]
        tableAll = dfP_filt[dfP_filt['Table Name'].isin(dfC['Table Name'].values) & (dfP_filt['Table Name'].isin(oneMode['Table Name'].values))]
        tables = tableAll['Table Name'].unique()

        client = fabric.FabricRestClient()

        print("Creating shortcuts...\n")
        for tableName in tables:      
            tablePath = 'Tables/' + tableName
            shortcutName = tableName.replace(' ','')
            request_body = {
            "path": 'Tables',
            "name": shortcutName,
            "target": {
                "oneLake": {
                "workspaceId": workspace_id,
                "itemId": sourceLakehouseId,
                "path": tablePath}
                }
            }

            try:
                response = client.post(f"/v1/workspaces/{destination_workspace_id}/items/{destination_lakehouse_id}/shortcuts",json=request_body)
                if response.status_code == 201:                
                    print(f"\u2022 The shortcut '{shortcutName}' was created in the '{destination_lakehouse}' lakehouse within the '{destination_workspace}' workspace. It is based on the '{tableName}' table in the '{dataset}' semantic model within the '{workspace}' workspace.\n")
                else:
                    print(response.status_code)
            except:
                print(f"ERROR: Failed to create a shortcut for the '{tableName}' table.")