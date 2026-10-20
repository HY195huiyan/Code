using UnityEditor;
using UnityEditor.IMGUI.Controls;
using UnityEngine;
using System.Collections.Generic;
using System.Linq;

// ==========================================
// 1. 数据类
// ==========================================
public class MeshInfo
{
    public Mesh mesh;
    
    // Faces
    public int zeroArea;
    public int zeroUVArea;
    public int lamina;
    public int invalidTriangle;

    // Edges
    public int hardEdges;

    // Vertices
    public int ghostVertices;
    public int coincidentVertices;

    public MeshInfo(Mesh m)
    {
        mesh = m;
        AnalyzeMesh();
    }

    private void AnalyzeMesh()
    {
        if (mesh == null) return;
        zeroArea = MeshChecker.CountZeroAreaFaces(mesh);
        zeroUVArea = MeshChecker.CountZeroUVArea(mesh);
        invalidTriangle = MeshChecker.CountInvalidTriangles(mesh);
        ghostVertices = MeshChecker.CountGhostVertices(mesh);
        coincidentVertices = MeshChecker.CountCoincidentVertices(mesh);
        
        var topoResult = MeshChecker.CheckTopology(mesh);
        hardEdges = topoResult.hardEdges;
        lamina = topoResult.lamina;
    }
}

// ==========================================
// 2. 检查逻辑类 (核心算法)
// ==========================================
public static class MeshChecker
{
    private const float TOLERANCE = 0.0001f;

    public static int CountZeroAreaFaces(Mesh mesh)
    {
        int count = 0;
        Vector3[] vertices = mesh.vertices;
        int[] triangles = mesh.triangles;
        for (int i = 0; i < triangles.Length; i += 3)
        {
            Vector3 p0 = vertices[triangles[i]];
            Vector3 p1 = vertices[triangles[i + 1]];
            Vector3 p2 = vertices[triangles[i + 2]];
            float area = Vector3.Cross(p1 - p0, p2 - p0).sqrMagnitude * 0.5f;
            if (area < TOLERANCE) count++;
        }
        return count;
    }

    public static int CountZeroUVArea(Mesh mesh)
    {
        int count = 0;
        Vector2[] uvs = mesh.uv;
        if (uvs == null || uvs.Length == 0) return 0;
        int[] triangles = mesh.triangles;
        for (int i = 0; i < triangles.Length; i += 3)
        {
            Vector2 uv0 = uvs[triangles[i]];
            Vector2 uv1 = uvs[triangles[i + 1]];
            Vector2 uv2 = uvs[triangles[i + 2]];
            float area = Mathf.Abs((uv0.x * (uv1.y - uv2.y) + uv1.x * (uv2.y - uv0.y) + uv2.x * (uv0.y - uv1.y))) * 0.5f;
            if (area < TOLERANCE) count++;
        }
        return count;
    }

    public static int CountInvalidTriangles(Mesh mesh)
    {
        int count = 0;
        int[] triangles = mesh.triangles;
        int vertexCount = mesh.vertexCount;
        for (int i = 0; i < triangles.Length; i += 3)
        {
            int v1 = triangles[i], v2 = triangles[i+1], v3 = triangles[i+2];
            if (v1 >= vertexCount || v2 >= vertexCount || v3 >= vertexCount) { count++; continue; }
            if (v1 == v2 || v2 == v3 || v1 == v3) count++;
        }
        return count;
    }

    public static int CountGhostVertices(Mesh mesh)
    {
        int count = 0;
        bool[] isUsed = new bool[mesh.vertexCount];
        int[] triangles = mesh.triangles;
        foreach (int index in triangles) if (index < isUsed.Length) isUsed[index] = true;
        foreach (bool used in isUsed) if (!used) count++;
        return count;
    }

    public static int CountCoincidentVertices(Mesh mesh)
    {
        int count = 0;
        Vector3[] vertices = mesh.vertices;
        Dictionary<Vector3Int, bool> hash = new Dictionary<Vector3Int, bool>();
        foreach (var v in vertices)
        {
            Vector3Int cell = new Vector3Int(
                Mathf.RoundToInt(v.x / TOLERANCE),
                Mathf.RoundToInt(v.y / TOLERANCE),
                Mathf.RoundToInt(v.z / TOLERANCE)
            );
            if (hash.ContainsKey(cell)) count++;
            else hash.Add(cell, true);
        }
        return count;
    }

    public struct TopoResult { public int hardEdges; public int lamina; }
    
    public static TopoResult CheckTopology(Mesh mesh)
    {
        TopoResult result = new TopoResult { hardEdges = 0, lamina = 0 };
        int[] triangles = mesh.triangles;
        Vector3[] vertices = mesh.vertices;
        Dictionary<(int, int), List<Vector3>> edgeData = new Dictionary<(int, int), List<Vector3>>();

        for (int i = 0; i < triangles.Length; i += 3)
        {
            int v0 = triangles[i], v1 = triangles[i + 1], v2 = triangles[i + 2];
            Vector3 faceNormal = Vector3.Cross(vertices[v1] - vertices[v0], vertices[v2] - vertices[v0]).normalized;
            AddEdgeToDict(edgeData, v0, v1, faceNormal);
            AddEdgeToDict(edgeData, v1, v2, faceNormal);
            AddEdgeToDict(edgeData, v2, v0, faceNormal);
        }

        foreach (var kvp in edgeData)
        {
            var faceNormals = kvp.Value;
            if (faceNormals.Count == 1) result.lamina++;
            else if (faceNormals.Count == 2)
            {
                float dot = Vector3.Dot(faceNormals[0], faceNormals[1]);
                if (dot < 0.5f) result.hardEdges++;
            }
        }
        return result;
    }

    private static void AddEdgeToDict(Dictionary<(int, int), List<Vector3>> dict, int a, int b, Vector3 normal)
    {
        var key = a < b ? (a, b) : (b, a);
        if (!dict.ContainsKey(key)) dict.Add(key, new List<Vector3>());
        dict[key].Add(normal);
    }
}

// ==========================================
// 3. 编辑器窗口类 (主界面)
// ==========================================
public class MeshCheckWindow : EditorWindow
{
    private List<MeshInfo> meshInfos = new List<MeshInfo>();
    private MultiColumnHeader multiColumnHeader;
    private Vector2 scrollPos;
    private string searchString = ""; 

    public enum ColumnID
    {
        Mesh, ZeroArea, ZeroUVArea, Lamina, InvalidTriangle, HardEdge, Ghost, Coincident
    }

    [MenuItem("Tools/Mesh Check UI")]
    public static void ShowWindow()
    {
        GetWindow<MeshCheckWindow>("Mesh Check UI");
    }

    private void OnEnable()
    {
        var columns = new MultiColumnHeaderState.Column[]
        {
            new MultiColumnHeaderState.Column { headerContent = new GUIContent("Mesh"), width = 200 },
            new MultiColumnHeaderState.Column { headerContent = new GUIContent("Zero Area"), width = 80 },
            new MultiColumnHeaderState.Column { headerContent = new GUIContent("Zero UV Area"), width = 100 },
            new MultiColumnHeaderState.Column { headerContent = new GUIContent("Lamina"), width = 80 },
            new MultiColumnHeaderState.Column { headerContent = new GUIContent("Invalid Tri"), width = 80 },
            new MultiColumnHeaderState.Column { headerContent = new GUIContent("Hard Edges"), width = 80 },
            new MultiColumnHeaderState.Column { headerContent = new GUIContent("Ghost"), width = 80 },
            new MultiColumnHeaderState.Column { headerContent = new GUIContent("Coincident"), width = 100 },
        };
        
        var state = new MultiColumnHeaderState(columns);
        multiColumnHeader = new MultiColumnHeader(state);
        multiColumnHeader.sortingChanged += OnSortingChanged;
        multiColumnHeader.ResizeToFit();
    }

    private void OnGUI()
    {
        DrawToolbar();
        GUILayout.BeginHorizontal();
        DrawLeftPanel();
        DrawMainTable();
        GUILayout.EndHorizontal();
    }

    private void DrawToolbar()
    {
        GUILayout.BeginHorizontal(EditorStyles.toolbar);
        if (GUILayout.Button("Check All", EditorStyles.toolbarButton, GUILayout.Width(80))) CheckAll();
        if (GUILayout.Button("Check Selected", EditorStyles.toolbarButton, GUILayout.Width(100))) CheckSelected();
        
        // ==========================================
        // 新增：Clear 按钮
        // ==========================================
        if (GUILayout.Button("Clear", EditorStyles.toolbarButton, GUILayout.Width(60))) ClearData();
        
        GUILayout.FlexibleSpace();
        
        GUILayout.Label("Mesh Search:", GUILayout.Width(80));
        searchString = GUILayout.TextField(searchString, EditorStyles.toolbarSearchField, GUILayout.Width(300));
        GUILayout.EndHorizontal();
    }

    private void DrawLeftPanel()
    {
        GUILayout.BeginVertical(GUI.skin.box, GUILayout.Width(150));
        
        GUILayout.Label("Select Faces", EditorStyles.boldLabel);
        if (GUILayout.Button("Zero Area")) ShowProblemPopup(ColumnID.ZeroArea);
        if (GUILayout.Button("Zero UV Area")) ShowProblemPopup(ColumnID.ZeroUVArea);
        if (GUILayout.Button("Lamina")) ShowProblemPopup(ColumnID.Lamina);
        if (GUILayout.Button("Invalid Tri")) ShowProblemPopup(ColumnID.InvalidTriangle);
        
        GUILayout.Space(10);
        GUILayout.Label("Select Edges", EditorStyles.boldLabel);
        if (GUILayout.Button("Hard Edges")) ShowProblemPopup(ColumnID.HardEdge);

        GUILayout.Space(10);
        GUILayout.Label("Select Vertices", EditorStyles.boldLabel);
        if (GUILayout.Button("Ghost")) ShowProblemPopup(ColumnID.Ghost);
        if (GUILayout.Button("Coincident")) ShowProblemPopup(ColumnID.Coincident);
        
        GUILayout.EndVertical();
    }

    private List<MeshInfo> GetFilteredMeshInfos()
    {
        if (string.IsNullOrEmpty(searchString)) return meshInfos;
        return meshInfos.Where(info => info.mesh.name.ToLower().Contains(searchString.ToLower())).ToList();
    }

    private void DrawMainTable()
    {
        GUILayout.BeginVertical();
        Rect headerRect = GUILayoutUtility.GetRect(0, 20, GUILayout.ExpandWidth(true));
        multiColumnHeader.OnGUI(headerRect, 0);

        scrollPos = GUILayout.BeginScrollView(scrollPos);
        var filteredInfos = GetFilteredMeshInfos();

        if (filteredInfos != null)
        {
            float rowHeight = 18f;
            for (int i = 0; i < filteredInfos.Count; i++)
            {
                Rect rowRect = GUILayoutUtility.GetRect(0, rowHeight, GUILayout.ExpandWidth(true));
                if (i % 2 == 1) EditorGUI.DrawRect(rowRect, new Color(0.2f, 0.2f, 0.2f, 0.2f));

                for (int col = 0; col < multiColumnHeader.state.columns.Length; col++)
                {
                    Rect cellRect = multiColumnHeader.GetCellRect(col, rowRect);
                    string value = GetCellData(filteredInfos[i], (ColumnID)col);
                    
                    if (value != "" && value != "0")
                        EditorGUI.LabelField(cellRect, new GUIContent(value), new GUIStyle(EditorStyles.label) { normal = { textColor = new Color(1f, 0.4f, 0.4f) } });
                    else
                        EditorGUI.LabelField(cellRect, value);
                }
                
                if (Event.current.type == EventType.MouseDown && rowRect.Contains(Event.current.mousePosition))
                {
                    var mf = filteredInfos[i].mesh;
                    var go = AssetDatabase.LoadAssetAtPath<GameObject>(AssetDatabase.GetAssetPath(mf));
                    if (go != null) Selection.activeObject = go;
                    Event.current.Use();
                }
            }
        }
        GUILayout.EndScrollView();
        GUILayout.EndVertical();
    }

    private string GetCellData(MeshInfo info, ColumnID col)
    {
        switch (col)
        {
            case ColumnID.Mesh: return info.mesh.name;
            case ColumnID.ZeroArea: return info.zeroArea > 0 ? info.zeroArea.ToString() : "";
            case ColumnID.ZeroUVArea: return info.zeroUVArea > 0 ? info.zeroUVArea.ToString() : "";
            case ColumnID.Lamina: return info.lamina > 0 ? info.lamina.ToString() : "";
            case ColumnID.InvalidTriangle: return info.invalidTriangle > 0 ? info.invalidTriangle.ToString() : "";
            case ColumnID.HardEdge: return info.hardEdges > 0 ? info.hardEdges.ToString() : "";
            case ColumnID.Ghost: return info.ghostVertices > 0 ? info.ghostVertices.ToString() : "";
            case ColumnID.Coincident: return info.coincidentVertices > 0 ? info.coincidentVertices.ToString() : "";
            default: return "";
        }
    }

    private void OnSortingChanged(MultiColumnHeader header)
    {
        int colIndex = header.sortedColumnIndex;
        if (colIndex < 0) return;
        bool ascending = header.IsSortedAscending(colIndex);

        meshInfos.Sort((a, b) =>
        {
            int result = 0;
            switch ((ColumnID)colIndex)
            {
                case ColumnID.Mesh: result = string.Compare(a.mesh.name, b.mesh.name); break;
                case ColumnID.ZeroArea: result = a.zeroArea.CompareTo(b.zeroArea); break;
                case ColumnID.ZeroUVArea: result = a.zeroUVArea.CompareTo(b.zeroUVArea); break;
                case ColumnID.Lamina: result = a.lamina.CompareTo(b.lamina); break;
                case ColumnID.InvalidTriangle: result = a.invalidTriangle.CompareTo(b.invalidTriangle); break;
                case ColumnID.HardEdge: result = a.hardEdges.CompareTo(b.hardEdges); break;
                case ColumnID.Ghost: result = a.ghostVertices.CompareTo(b.ghostVertices); break;
                case ColumnID.Coincident: result = a.coincidentVertices.CompareTo(b.coincidentVertices); break;
                default: result = 0; break;
            }
            return ascending ? result : -result;
        });
        Repaint();
    }

    private void CheckAll()
    {
        meshInfos.Clear();
        var allMeshes = UnityEngine.Object.FindObjectsByType<MeshFilter>()
            .Select(mf => mf.sharedMesh)
            .Where(m => m != null)
            .Distinct();

        foreach (var m in allMeshes) meshInfos.Add(new MeshInfo(m));
        OnSortingChanged(multiColumnHeader);
    }

    private void CheckSelected()
    {
        meshInfos.Clear();
        var selectedObjects = Selection.gameObjects;
        foreach (var go in selectedObjects)
        {
            var mf = go.GetComponentInChildren<MeshFilter>();
            if (mf != null && mf.sharedMesh != null)
            {
                if (!meshInfos.Any(info => info.mesh == mf.sharedMesh))
                    meshInfos.Add(new MeshInfo(mf.sharedMesh));
            }
        }
        OnSortingChanged(multiColumnHeader);
    }

    private void ClearData()
    {
        meshInfos.Clear();       // 清空数据列表
        searchString = "";       // 清空搜索框
        scrollPos = Vector2.zero; // 重置滚动条到顶部
        Repaint();               // 刷新界面
    }

    private void ShowProblemPopup(ColumnID targetCol)
    {
        var currentList = GetFilteredMeshInfos(); 

        List<MeshInfo> problemMeshes = currentList.Where(info => {
            string val = GetCellData(info, targetCol);
            return !string.IsNullOrEmpty(val) && val != "0";
        }).ToList();

        if (problemMeshes.Count == 0)
        {
            EditorUtility.DisplayDialog("检查结果", $"没有发现任何模型包含 {targetCol} 异常！", "好的");
            return;
        }

        var popup = new ProblemListPopupContent(problemMeshes, targetCol);
        PopupWindow.Show(new Rect(Event.current.mousePosition.x, Event.current.mousePosition.y, 0, 0), popup);
    }
}

// ==========================================
// 4. 弹出的列表 UI 窗口
// ==========================================
public class ProblemListPopupContent : PopupWindowContent
{
    private List<MeshInfo> problems;
    private MeshCheckWindow.ColumnID targetCol;
    private Vector2 scrollPos;

    public ProblemListPopupContent(List<MeshInfo> problems, MeshCheckWindow.ColumnID targetCol)
    {
        this.problems = problems;
        this.targetCol = targetCol;
    }

    public override Vector2 GetWindowSize()
    {
        float height = Mathf.Clamp(problems.Count * 22 + 40, 100, 400);
        return new Vector2(300, height);
    }

    public override void OnGUI(Rect rect)
    {
        GUILayout.Label($"包含 {targetCol} 异常的模型 ({problems.Count}个):", EditorStyles.boldLabel);
        GUILayout.Space(5);

        scrollPos = GUILayout.BeginScrollView(scrollPos);
        foreach (var info in problems)
        {
            GUILayout.BeginHorizontal();
            
            if (GUILayout.Button(info.mesh.name, EditorStyles.label))
            {
                string path = AssetDatabase.GetAssetPath(info.mesh);
                var obj = AssetDatabase.LoadAssetAtPath<Object>(path);
                EditorGUIUtility.PingObject(obj);
                Selection.activeObject = obj;

                FocusInScene(info.mesh);
            }

            GUILayout.FlexibleSpace();
            
            string val = GetCellData(info, targetCol);
            GUILayout.Label(val, EditorStyles.boldLabel, GUILayout.Width(40));
            
            GUILayout.EndHorizontal();
        }
        GUILayout.EndScrollView();
    }

    private void FocusInScene(Mesh mesh)
    {
        var allObjects = UnityEngine.Object.FindObjectsByType<MeshFilter>();
        foreach (var mf in allObjects)
        {
            if (mf.sharedMesh == mesh)
            {
                Selection.activeGameObject = mf.gameObject;
                if (SceneView.lastActiveSceneView != null)
                {
                    SceneView.lastActiveSceneView.FrameSelected();
                }
                break;
            }
        }
    }

    private string GetCellData(MeshInfo info, MeshCheckWindow.ColumnID col)
    {
        switch (col)
        {
            case MeshCheckWindow.ColumnID.ZeroArea: return info.zeroArea.ToString();
            case MeshCheckWindow.ColumnID.ZeroUVArea: return info.zeroUVArea.ToString();
            case MeshCheckWindow.ColumnID.Lamina: return info.lamina.ToString();
            case MeshCheckWindow.ColumnID.InvalidTriangle: return info.invalidTriangle.ToString();
            case MeshCheckWindow.ColumnID.HardEdge: return info.hardEdges.ToString();
            case MeshCheckWindow.ColumnID.Ghost: return info.ghostVertices.ToString();
            case MeshCheckWindow.ColumnID.Coincident: return info.coincidentVertices.ToString();
            default: return "";
        }
    }
}