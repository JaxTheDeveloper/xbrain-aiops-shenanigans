import networkx as nx
import matplotlib.pyplot as plt
import numpy as np

def plot_beautiful_clique():
    # use a subtle, clean background color
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), facecolor='#f8f9fa')
    
    # 1. define the base historical clique (fully connected K_5 graph)
    hist_nodes = [f"H{i}" for i in range(1, 6)]
    g_base = nx.complete_graph(len(hist_nodes))
    g_base = nx.relabel_nodes(g_base, {i: hist_nodes[i] for i in range(len(hist_nodes))})
    
    # 2. lock the geometry so it stays identical across both plots
    pos = nx.circular_layout(hist_nodes)
    # shift the historical cluster to the left
    for k in pos:
        pos[k] = pos[k] - np.array([0.5, 0])
        
    # hardcode the query node position on the right
    pos['Query'] = np.array([1.5, 0]) 
    
    # --- left plot: in-distribution ---
    ax1 = axes[0]
    g_in = g_base.copy()
    g_in.add_node('Query')
    
    # query successfully connects to historical nodes
    query_edges = [('Query', 'H1'), ('Query', 'H2'), ('Query', 'H3'), ('Query', 'H4')]
    g_in.add_edges_from(query_edges)
    
    # draw historical nodes (blue) and edges (light grey)
    nx.draw_networkx_nodes(g_in, pos, nodelist=hist_nodes, node_color='#4A90E2', 
                           node_size=1500, edgecolors='white', linewidths=2, ax=ax1)
    nx.draw_networkx_edges(g_in, pos, edgelist=g_base.edges(), edge_color='#B0BEC5', 
                           width=1.5, ax=ax1)
    
    # draw query node (green) and dashed connection edges
    nx.draw_networkx_nodes(g_in, pos, nodelist=['Query'], node_color='#2ECC71', 
                           node_size=1800, edgecolors='white', linewidths=2, ax=ax1)
    nx.draw_networkx_edges(g_in, pos, edgelist=query_edges, edge_color='#2ECC71', 
                           width=2, style='dashed', ax=ax1)
    
    nx.draw_networkx_labels(g_in, pos, font_color='white', font_weight='bold', font_size=12, ax=ax1)
    
    ax1.set_title("in-distribution: maximal clique formation\n(safety boundary satisfied)", 
                  fontsize=14, fontweight='bold', color='#333333', pad=20)
    ax1.axis('off')
    
    # --- right plot: out-of-distribution ---
    ax2 = axes[1]
    g_ood = g_base.copy()
    g_ood.add_node('Query')
    
    # draw historical nodes and edges exactly as before
    nx.draw_networkx_nodes(g_ood, pos, nodelist=hist_nodes, node_color='#4A90E2', 
                           node_size=1500, edgecolors='white', linewidths=2, ax=ax2)
    nx.draw_networkx_edges(g_ood, pos, edgelist=g_base.edges(), edge_color='#B0BEC5', 
                           width=1.5, ax=ax2)
    
    # draw isolated query node (red), no edges
    nx.draw_networkx_nodes(g_ood, pos, nodelist=['Query'], node_color='#E74C3C', 
                           node_size=1800, edgecolors='white', linewidths=2, ax=ax2)
    
    nx.draw_networkx_labels(g_ood, pos, font_color='white', font_weight='bold', font_size=12, ax=ax2)
    
    ax2.set_title("out-of-distribution: topological isolation\n(anomaly detected -> escalate)", 
                  fontsize=14, fontweight='bold', color='#333333', pad=20)
    ax2.axis('off')
    
    # finalize and save
    plt.tight_layout(pad=3.0)
    plt.savefig("improved_clique.png", dpi=300, bbox_inches='tight', facecolor=fig.get_facecolor())
    print("visualization saved to improved_clique.png")
    plt.show()

if __name__ == "__main__":
    plot_beautiful_clique()