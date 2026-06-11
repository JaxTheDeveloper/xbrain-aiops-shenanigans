from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.network import APIGateway
from diagrams.aws.security import IAM
from diagrams.aws.analytics import ElasticsearchService # Changed to ensure compatibility
from diagrams.aws.ml import Sagemaker
from diagrams.aws.general import User, InternetAlt1

# Generates "agentcore_architecture.png"
with Diagram("AgentCore Architecture: Space Tourism VR Platform", show=False, direction="LR", filename="agentcore_architecture"):
    
    tourist = User("VR Tourist\n(Vue Frontend)")
    nasa_api = InternetAlt1("NASA Horizons API\n(External Ephemeris)")
    
    with Cluster("AWS Cloud Boundary"):
        api_gw = APIGateway("API Gateway\n(Entry Point)")
        iam = IAM("Agent Execution Role\n(Strict IAM Identity)")
        
        with Cluster("Amazon Bedrock"):
            
            with Cluster("AgentCore Runtime Environment"):
                agent_runtime = Sagemaker("Managed Agent Runtime\n(Session & State Orchestrator)")
                fm = Sagemaker("Foundation Model\n(Anthropic Claude 3.5)")
                
                # Internal interaction within the runtime
                agent_runtime - Edge(color="purple", style="bold") - fm
            
            with Cluster("Knowledge Bases (RAG)"):
                # Using ElasticsearchService icon but labeling it as OpenSearch
                kb_db = ElasticsearchService("Amazon OpenSearch\n(Mission Lore & Educational Text)")
                
            with Cluster("Action Groups (Tools)"):
                ag_lambda = Lambda("Telemetry Proxy Lambda\n(Calculates ISS Passes)")

        # Structural Connections & Permissions
        agent_runtime - Edge(style="dotted", color="red", label="Assumes Role") - iam
        
        # Invocation Pathways
        api_gw >> Edge(color="darkblue", label="1. InvokeAgent API") >> agent_runtime
        
        # Tool and KB connections managed by Runtime
        agent_runtime >> Edge(color="darkgreen", label="2a. Retrieve Context") >> kb_db
        agent_runtime >> Edge(color="darkorange", label="2b. Trigger Action via OpenAPI") >> ag_lambda
        
    # External Connections
    tourist >> Edge(color="black", label="Query + Geospatial Coordinates") >> api_gw
    ag_lambda >> Edge(color="black", label="Query Orbit Data") >> nasa_api
    
    # Return Paths
    nasa_api >> ag_lambda
    ag_lambda >> agent_runtime
    kb_db >> agent_runtime
    agent_runtime >> api_gw
    api_gw >> Edge(color="black", label="Synthesized VR Response") >> tourist