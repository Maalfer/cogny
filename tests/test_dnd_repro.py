import sys
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QByteArray, QDataStream, QIODevice, Qt, QModelIndex
from app.models.note_model import NoteTreeModel
from app.database.manager import DatabaseManager

# Mock DB
class MockDB:
    def __init__(self):
        self.notes = {}
        self.counter = 1
    
    def _get_connection(self):
        # We mock load_notes so this isn't needed
        return None
        
    def add_note(self, title, parent_id=None, is_folder=False):
        nid = self.counter
        self.counter += 1
        self.notes[nid] = {'title': title, 'parent_id': parent_id, 'is_folder': is_folder}
        return nid
        
    def move_note_to_parent(self, note_id, new_parent_id):
        if note_id in self.notes:
            self.notes[note_id]['parent_id'] = new_parent_id

class TestDnDRepro(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)

    def setUp(self):
        self.db = MockDB()
        self.model = NoteTreeModel(self.db)
        
        # Setup Setup
        # 1: DNS (Leaf)
        # 2: Correo (Leaf)
        # 3: Kubernetes (Folder)
        #    4: KubeChild
        
        self.dns_id = self.model.add_note("DNS", None)
        self.correo_id = self.model.add_note("Correo", None)
        self.kube_id = self.model.add_note("Kubernetes", None)
        self.kube_child_id = self.model.add_note("KubeChild", self.kube_id)
        
        # Verify Initial State
        self.assertEqual(self.model.rowCount(QModelIndex()), 3)
        self.assertEqual(self.model.item(0).text(), "DNS")
        self.assertEqual(self.model.item(1).text(), "Correo")
        self.assertEqual(self.model.item(2).text(), "Kubernetes")
        
        kube_item = self.model.item(2)
        self.assertEqual(kube_item.rowCount(), 1)
        
    def test_drop_on_sibling_preserves_folder(self):
        print("\n--- Testing Drop DNS on Correo ---")
        
        # Get Items
        dns_item = self.model.item(0)
        correo_item = self.model.item(1)
        kube_item = self.model.item(2)
        
        dns_idx = self.model.indexFromItem(dns_item)
        correo_idx = self.model.indexFromItem(correo_item)
        
        # Create MimeData for DNS
        mime = self.model.mimeData([dns_idx])
        
        # DROP ON CORREO
        # Action: Move
        # Row: -1 (Drop On)
        # Parent: Correo Index
        
        print(f"Dropping IDs: {[dns_item.note_id]} on Parent: {correo_item.text()} (Row -1)")
        
        result = self.model.dropMimeData(mime, Qt.MoveAction, -1, -1, correo_idx)
        
        print(f"Drop Result: {result}")
        
        # Checks
        # 1. DNS should be sibling of Correo
        # 2. Kubernetes should still exist
        
        # Reload model structure to be sure
        root = self.model.invisibleRootItem()
        count = root.rowCount()
        print(f"Root Row Count: {count}")
        for i in range(count):
            print(f"Row {i}: {root.child(i).text()}")
            
        self.assertEqual(count, 3, "Should still have 3 root items")
        
        names = [root.child(i).text() for i in range(count)]
        self.assertIn("Kubernetes", names, "Kubernetes folder must exist")
        self.assertIn("DNS", names)
        
        # Verify Kube children
        new_kube_idx = self.model.index(names.index("Kubernetes"), 0)
        new_kube_item = self.model.itemFromIndex(new_kube_idx)
        print(f"Kubernetes Children: {new_kube_item.rowCount()}")
        self.assertEqual(new_kube_item.rowCount(), 1, "Kubernetes should still have child")

if __name__ == '__main__':
    unittest.main()
