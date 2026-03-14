"""
Skill module tests
"""
from pathlib import Path

from src import Skill, SkillRegistry


class TestSkill:
    """Test Skill class"""
    
    def test_skill_creation(self):
        """Test creating Skill object"""
        skill = Skill(
            name="test",
            description="Test skill",
            content="## Content",
            metadata={"author": "test"}
        )
        assert skill.name == "test"
        assert skill.description == "Test skill"
        assert skill.content == "## Content"
        assert skill.metadata == {"author": "test"}


class TestSkillRegistry:
    """Test SkillRegistry class"""
    
    def test_load_from_directory(self):
        """Test loading skills from directory"""
        skills_dir = Path(__file__).parent.parent / "skills"
        registry = SkillRegistry(skills_dir)
        
        # Verify skills were loaded
        skills = registry.list_all()
        assert len(skills) > 0
        
        # Verify each skill has correct structure
        for skill in skills:
            assert skill.name
            assert skill.description
            assert skill.content
            assert skill.skill_path
    
    def test_yaml_frontmatter_parsing(self):
        """Test YAML frontmatter parsing"""
        skills_dir = Path(__file__).parent.parent / "skills"
        registry = SkillRegistry(skills_dir)

        # Get mut_los skill (has frontmatter)
        mut_los = registry.get("mut_los")
        assert mut_los is not None
        assert mut_los.name == "mut_los"
        assert "MUT_LOS" in mut_los.description
        # metadata field contains nested metadata from frontmatter
        assert isinstance(mut_los.metadata, dict)

    def test_read_skill_content(self):
        """Test reading skill content"""
        skills_dir = Path(__file__).parent.parent / "skills"
        registry = SkillRegistry(skills_dir)

        # Read mut_los skill content
        content = registry.read_skill_content("mut_los")
        assert content
        assert "##" in content  # Should have markdown headers
        assert "---" not in content[:100]  # Should not contain frontmatter
    
    def test_read_nonexistent_skill(self):
        """Test reading non-existent skill"""
        registry = SkillRegistry()
        result = registry.read_skill_content("nonexistent")
        assert "not found" in result


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
