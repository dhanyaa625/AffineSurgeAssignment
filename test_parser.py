import pytest
from main import parse_markdown_to_nodes, ParsedNode

def test_hierarchical_parenting():
    """Test that a basic hierarchy creates proper parent-child relationships."""
    md = "# H1\n## H2\n### H3"
    nodes = parse_markdown_to_nodes(md)
    # nodes[0] is Document Root
    # nodes[1] is H1, nodes[2] is H2, nodes[3] is H3
    assert len(nodes) == 4
    assert nodes[1].heading == "H1"
    assert nodes[1].parent.heading == "Document Root"
    
    assert nodes[2].heading == "H2"
    assert nodes[2].parent == nodes[1]
    
    assert nodes[3].heading == "H3"
    assert nodes[3].parent == nodes[2]

def test_skipped_heading_levels():
    """Test that if a heading level is skipped (e.g. H2 -> H4), the H4 is correctly parented to H2."""
    md = "## H2\n#### H4\n### H3"
    nodes = parse_markdown_to_nodes(md)
    # 0: Root, 1: H2, 2: H4, 3: H3
    assert nodes[2].heading == "H4"
    assert nodes[2].parent == nodes[1]  # Parent of H4 is H2
    
    assert nodes[3].heading == "H3"
    assert nodes[3].parent == nodes[1]  # Parent of H3 is H2 (because H3 pops H4 off the stack)

def test_logical_path_deduplication():
    """Test that two headings with the exact same name under the same parent get unique logical paths."""
    md = "# Parent\n## Duplicate\n## Duplicate"
    nodes = parse_markdown_to_nodes(md)
    # 0: Root, 1: Parent, 2: Duplicate, 3: Duplicate
    assert nodes[2].logical_path == "Document Root/Parent/Duplicate"
    assert nodes[3].logical_path == "Document Root/Parent/Duplicate [2]"
