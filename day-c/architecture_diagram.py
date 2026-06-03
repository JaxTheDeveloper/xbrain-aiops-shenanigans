from diagrams import Diagram, Cluster, Edge
from diagrams.programming.language import Python
from diagrams.onprem.queue import Nats
from diagrams.onprem.database import Postgresql
from diagrams.onprem.monitoring import Grafana

def main():
    # filename saves as architecture.png
    with Diagram("pythonic aiops pipeline with nats and tailscale", show=False, filename="architecture", direction="LR"):
        
        # tailscale acts as the secure network overlay encapsulating all components
        with Cluster("tailscale secure private mesh network"):
            
            with Cluster("1. service & 2. collection"):
                # fastapi replaces spring; otel python sdk handles collection in-process
                payment_app = Python("fastapi payment service\n(otel python sdk)")
                
            with Cluster("3. transport"):
                # nats jetstream acts as the ultra-lightweight alternative to kafka
                broker = Nats("nats jetstream\nevent broker")
                
            with Cluster("4. processing"):
                # faust or bytewax provides python-native stream processing instead of flink
                stream_processor = Python("faust / bytewax\nstream engine")
                
            with Cluster("5. storage"):
                # timescaledb (postgres extension) stores time-series data and features
                db = Postgresql("timescaledb\n(feature & log store)")
                
            with Cluster("6. query / ml"):
                dashboard = Grafana("grafana dashboard")
                ai_model = Python("scikit-learn\nisolation forest")

        # pipeline data flow
        payment_app >> Edge(label="pub", color="blue") >> broker
        broker >> Edge(label="sub", color="blue") >> stream_processor
        stream_processor >> Edge(label="insert") >> db
        
        # storage serving visualization and machine learning inference
        db >> dashboard
        db >> ai_model
        ai_model >> Edge(style="dashed", color="red", label="anomaly alerts") >> dashboard

if __name__ == "__main__":
    main()