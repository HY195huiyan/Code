using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using System.IO;
using System.Linq;

public class BatchFBXImportTool : EditorWindow
{
    // Per-mesh check result
    public class MeshCheckResult
    {
        public string meshName;
        public Mesh meshRef; // 新增：保存 Mesh 的引用，用于定位
        public List<string> namingIssues = new List<string>();
        public List<string> materialIssues = new List<string>();
        public List<string> uvIssues = new List<string>();

        public bool HasAnyIssue => namingIssues.Count > 0 || materialIssues.Count > 0 || uvIssues.Count > 0;

        public int TotalIssueCount => namingIssues.Count + materialIssues.Count + uvIssues.Count;
    }

    // Stores the check result for each FBX
    public class FBXReport
    {
        public string assetPath;
        public string fileName;
        public List<MeshCheckResult> meshResults = new List<MeshCheckResult>();

        public int TotalIssueCount => meshResults.Sum(r => r.TotalIssueCount);
        public int IssueMeshCount => meshResults.Count(r => r.HasAnyIssue);
    }

    private List<FBXReport> reports = new List<FBXReport>();
    private Vector2 scrollPos;

    // Adds a menu item in the top toolbar (under Tools menu)
    [MenuItem("Tools/Batch Import FBX", false, 1)]
    public static void ShowWindow()
    {
        GetWindow<BatchFBXImportTool>("FBX Import Report");
    }

    private void OnGUI()
    {
        EditorGUILayout.LabelField("FBX Batch Import Check Report", EditorStyles.boldLabel);
        EditorGUILayout.Space();

        if (GUILayout.Button("Select FBX Files and Import", GUILayout.Height(30)))
        {
            ImportFBXFiles();
        }

        EditorGUILayout.Space();

        if (reports.Count == 0)
        {
            EditorGUILayout.HelpBox("No import records yet. Click the button above to import FBX files.", MessageType.Info);
            return;
        }

        EditorGUILayout.LabelField($"Checked {reports.Count} file(s)", EditorStyles.miniLabel);
        scrollPos = EditorGUILayout.BeginScrollView(scrollPos);

        foreach (var report in reports)
        {
            EditorGUILayout.BeginVertical("box");

            // One button per FBX file
            string btnText = report.fileName;
            if (report.TotalIssueCount > 0)
                btnText += $"  ⚠️ ({report.IssueMeshCount} mesh(es) with {report.TotalIssueCount} issue(s))";
            else
                btnText += "  ✅";

            if (GUILayout.Button(btnText, GUILayout.Height(25)))
            {
                ShowDetailWindow(report);
            }

            // Brief preview
            if (report.TotalIssueCount > 0)
            {
                foreach (var mesh in report.meshResults.Where(m => m.HasAnyIssue).Take(2))
                {
                    EditorGUILayout.LabelField($"  • {mesh.meshName} ({mesh.TotalIssueCount} issue(s))", EditorStyles.miniLabel);
                }
                if (report.IssueMeshCount > 2)
                    EditorGUILayout.LabelField($"  ... and {report.IssueMeshCount - 2} more mesh(es) with issues", EditorStyles.miniLabel);
            }

            EditorGUILayout.EndVertical();
            EditorGUILayout.Space(2);
        }

        EditorGUILayout.EndScrollView();
    }

    private void ImportFBXFiles()
    {
        string[] paths = SelectFBXFiles();
        if (paths == null || paths.Length == 0)
            return;

        reports.Clear();

        string targetDir = "Assets/ImportedFBX";
        if (!Directory.Exists(targetDir))
            Directory.CreateDirectory(targetDir);

        foreach (string sourcePath in paths)
        {
            string fileName = Path.GetFileName(sourcePath);
            string destPath = Path.Combine(targetDir, fileName).Replace("\\", "/");

            if (File.Exists(destPath))
            {
                AssetDatabase.DeleteAsset(destPath);
            }
            File.Copy(sourcePath, destPath, true);
            AssetDatabase.ImportAsset(destPath, ImportAssetOptions.ForceUpdate);

            CheckFBX(destPath);
        }

        AssetDatabase.Refresh();
        Debug.Log($"Batch import complete. Processed {reports.Count} FBX file(s).");
    }

    private string[] SelectFBXFiles()
    {
        string folder = EditorUtility.OpenFolderPanel("Select Folder Containing FBX Files", "", "");
        if (string.IsNullOrEmpty(folder))
            return null;

        string[] fbxFiles = Directory.GetFiles(folder, "*.fbx", SearchOption.TopDirectoryOnly);
        if (fbxFiles.Length == 0)
        {
            EditorUtility.DisplayDialog("No FBX Found", "No .fbx files were found in the selected folder.", "OK");
            return null;
        }

        return fbxFiles;
    }

    private void CheckFBX(string assetPath)
    {
        FBXReport report = new FBXReport();
        report.assetPath = assetPath;
        report.fileName = Path.GetFileNameWithoutExtension(assetPath);

        GameObject fbxAsset = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
        if (fbxAsset == null)
        {
            report.meshResults.Add(new MeshCheckResult
            {
                meshName = "(root)",
                namingIssues = { "Failed to load the FBX asset." }
            });
            reports.Add(report);
            return;
        }

        // Iterate over every MeshRenderer / SkinnedMeshRenderer and check per mesh
        Renderer[] renderers = fbxAsset.GetComponentsInChildren<Renderer>(true);
        if (renderers.Length == 0)
        {
            report.meshResults.Add(new MeshCheckResult
            {
                meshName = "(root)",
                namingIssues = { "No Renderer components found. This may not be a valid model." }
            });
            reports.Add(report);
            return;
        }

        foreach (Renderer renderer in renderers)
        {
            MeshCheckResult result = new MeshCheckResult();
            result.meshName = renderer.gameObject.name;

            // 1. Naming check
            CheckModelNaming(renderer.gameObject, result);

            // 2. Material check
            CheckMaterials(renderer, result);

            // 3. UV check (only if a mesh exists)
            Mesh mesh = null;
            if (renderer is MeshRenderer mr)
            {
                var mf = mr.GetComponent<MeshFilter>();
                if (mf != null) mesh = mf.sharedMesh;
            }
            else if (renderer is SkinnedMeshRenderer smr)
            {
                mesh = smr.sharedMesh;
            }

            // 保存 Mesh 引用供 UI 定位使用
            result.meshRef = mesh;

            if (mesh != null)
                CheckUV(mesh, result);
            else
                result.uvIssues.Add("No mesh assigned to this renderer.");

            report.meshResults.Add(result);
        }

        reports.Add(report);
    }

    private void CheckModelNaming(GameObject go, MeshCheckResult result)
    {
        string name = go.name.ToLower().Trim();
        if (string.IsNullOrEmpty(name)) return;

        string[] suspiciousPatterns = new string[]
        {
            "polycylinder", "polycube", "polysphere", "polytorus", "polyplane", "polycone", "poly",
            "pcube", "pcylinder", "psphere", "ptorus", "pplane", "pcone",
            "p cube", "p cylinder", "p sphere", "p torus", "p plane", "p cone",
            "cube", "cylinder", "sphere", "torus", "plane", "cone",
            "mesh", "object", "group", "null", "locator"
        };

        foreach (string pattern in suspiciousPatterns)
        {
            if (name == pattern || name.StartsWith(pattern))
            {
                result.namingIssues.Add($"Name '{go.name}' looks like a default placeholder name.");
                return;
            }
            if (name.StartsWith(pattern) && name.Length > pattern.Length && char.IsDigit(name[pattern.Length]))
            {
                result.namingIssues.Add($"Name '{go.name}' looks like a default placeholder name.");
                return;
            }
        }
    }

    private void CheckMaterials(Renderer renderer, MeshCheckResult result)
    {
        Material[] mats = renderer.sharedMaterials;
        if (mats == null || mats.Length == 0)
        {
            result.materialIssues.Add("No material assigned.");
            return;
        }

        foreach (Material mat in mats)
        {
            if (mat == null)
            {
                result.materialIssues.Add("Material slot contains a null material.");
                return;
            }

            if (mat.name.Contains("Default-Diffuse") ||
                mat.name.Contains("Default Diffuse") ||
                AssetDatabase.GetAssetPath(mat).Contains("Default-Diffuse"))
            {
                result.materialIssues.Add($"Uses Unity default diffuse material '{mat.name}' (likely no material in source FBX).");
                return;
            }
        }
    }

    private void CheckUV(Mesh mesh, MeshCheckResult result)
    {
        if (mesh.uv == null || mesh.uv.Length == 0)
        {
            result.uvIssues.Add("Mesh has no UV data.");
            return;
        }

        Vector2[] uvs = mesh.uv;
        int outOfRangeCount = 0;
        float minU = float.MaxValue, maxU = float.MinValue;
        float minV = float.MaxValue, maxV = float.MinValue;

        foreach (var uv in uvs)
        {
            if (uv.x < -0.001f || uv.x > 1.001f || uv.y < -0.001f || uv.y > 1.001f)
                outOfRangeCount++;

            minU = Mathf.Min(minU, uv.x);
            maxU = Mathf.Max(maxU, uv.x);
            minV = Mathf.Min(minV, uv.y);
            maxV = Mathf.Max(maxV, uv.y);
        }

        if (outOfRangeCount > 0)
        {
            result.uvIssues.Add(
                $"{outOfRangeCount}/{uvs.Length} UV(s) outside 0–1 " +
                $"(U: {minU:F2} ~ {maxU:F2}, V: {minV:F2} ~ {maxV:F2})."
            );
        }
    }

    private void ShowDetailWindow(FBXReport report)
    {
        FBXDetailWindow.ShowWindow(report);
    }

    // Standalone detail window with scrollable per-mesh list
    public class FBXDetailWindow : EditorWindow
    {
        private FBXReport report;
        private Vector2 scrollPos;

        public static void ShowWindow(FBXReport rep)
        {
            var window = GetWindow<FBXDetailWindow>("FBX Details");
            window.report = rep;
            window.minSize = new Vector2(600, 350); // 稍微加宽了一点，适应按钮
            window.Show();
        }

        private void OnGUI()
        {
            if (report == null)
            {
                EditorGUILayout.HelpBox("No report data.", MessageType.Error);
                return;
            }

            EditorGUILayout.LabelField($"File: {report.fileName}", EditorStyles.boldLabel);
            EditorGUILayout.LabelField($"Path: {report.assetPath}", EditorStyles.miniLabel);
            EditorGUILayout.LabelField($"Meshes: {report.meshResults.Count}   |   Meshes with issues: {report.IssueMeshCount}", EditorStyles.miniLabel);
            EditorGUILayout.Space();

            if (report.TotalIssueCount == 0)
            {
                EditorGUILayout.HelpBox("✅ No issues found in this file.", MessageType.Info);
            }

            // Column header
            EditorGUILayout.BeginHorizontal(EditorStyles.toolbar);
            EditorGUILayout.LabelField("Mesh (Click to Ping)", EditorStyles.toolbarButton, GUILayout.Width(180));
            EditorGUILayout.LabelField("Naming", EditorStyles.toolbarButton, GUILayout.Width(60));
            EditorGUILayout.LabelField("Material", EditorStyles.toolbarButton, GUILayout.Width(60));
            EditorGUILayout.LabelField("UV", EditorStyles.toolbarButton, GUILayout.Width(60));
            EditorGUILayout.LabelField("Details", EditorStyles.toolbarButton);
            EditorGUILayout.EndHorizontal();

            scrollPos = EditorGUILayout.BeginScrollView(scrollPos);

            foreach (var mesh in report.meshResults)
            {
                // One row per mesh
                EditorGUILayout.BeginHorizontal("box");

                // 使用 GUI.Button 来让名字可以点击
                if (GUILayout.Button(mesh.meshName, EditorStyles.label, GUILayout.Width(180)))
                {
                    PingMesh(mesh.meshRef);
                }

                EditorGUILayout.LabelField(mesh.namingIssues.Count > 0 ? "⚠️" : "✅", GUILayout.Width(60));
                EditorGUILayout.LabelField(mesh.materialIssues.Count > 0 ? "⚠️" : "✅", GUILayout.Width(60));
                EditorGUILayout.LabelField(mesh.uvIssues.Count > 0 ? "⚠️" : "✅", GUILayout.Width(60));

                // Combine all issues for this mesh into one readable string
                List<string> allIssues = new List<string>();
                allIssues.AddRange(mesh.namingIssues);
                allIssues.AddRange(mesh.materialIssues);
                allIssues.AddRange(mesh.uvIssues);

                if (allIssues.Count == 0)
                {
                    EditorGUILayout.LabelField("No issues.", EditorStyles.miniLabel);
                }
                else
                {
                    EditorGUILayout.LabelField(string.Join(" | ", allIssues), EditorStyles.wordWrappedMiniLabel);
                }

                EditorGUILayout.EndHorizontal();
            }

            EditorGUILayout.EndScrollView();

            EditorGUILayout.Space();
            if (GUILayout.Button("Ping FBX Asset in Project Window", GUILayout.Height(25)))
            {
                var obj = AssetDatabase.LoadAssetAtPath<GameObject>(report.assetPath);
                if (obj != null)
                    EditorGUIUtility.PingObject(obj);
            }
        }

        // 定位 Mesh 的专用方法
        private void PingMesh(Mesh mesh)
        {
            if (mesh == null)
            {
                Debug.LogWarning("Mesh reference is null, cannot ping.");
                return;
            }

            // 1. 在 Project 窗口中高亮（Ping）该 Mesh 文件（通常是 FBX 内的子资源）
            EditorGUIUtility.PingObject(mesh);

            // 2. 同时在 Inspector 面板中选中该 Mesh 资源，方便直接查看属性
            Selection.activeObject = mesh;
        }
    }
}