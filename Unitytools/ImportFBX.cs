using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using System.IO;
using System.Linq;

public class BatchFBXImportTool : EditorWindow
{
    // Stores the check result for each FBX
    private class FBXReport
    {
        public string assetPath;
        public string fileName;
        public List<string> issues = new List<string>();
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
            if (report.issues.Count > 0)
                btnText += $"  ⚠️ ({report.issues.Count} issue(s))";
            else
                btnText += "  ✅";

            if (GUILayout.Button(btnText, GUILayout.Height(25)))
            {
                ShowDetailWindow(report);
            }

            // Brief preview
            if (report.issues.Count > 0)
            {
                foreach (var issue in report.issues.Take(2))
                {
                    EditorGUILayout.LabelField("  • " + issue, EditorStyles.miniLabel);
                }
                if (report.issues.Count > 2)
                    EditorGUILayout.LabelField($"  ... and {report.issues.Count - 2} more issue(s)", EditorStyles.miniLabel);
            }

            EditorGUILayout.EndVertical();
            EditorGUILayout.Space(2);
        }

        EditorGUILayout.EndScrollView();
    }

    private void ImportFBXFiles()
    {
        // Open folder selection dialog
        string[] paths = SelectFBXFiles();
        if (paths == null || paths.Length == 0)
            return;

        reports.Clear();

        // Ensure the target directory exists
        string targetDir = "Assets/ImportedFBX";
        if (!Directory.Exists(targetDir))
            Directory.CreateDirectory(targetDir);

        foreach (string sourcePath in paths)
        {
            string fileName = Path.GetFileName(sourcePath);
            string destPath = Path.Combine(targetDir, fileName).Replace("\\", "/");

            // Copy the file into the Assets folder (Unity only recognizes assets under Assets)
            if (File.Exists(destPath))
            {
                // If it already exists, delete it first, then copy again to ensure refresh
                AssetDatabase.DeleteAsset(destPath);
            }
            File.Copy(sourcePath, destPath, true);
            AssetDatabase.ImportAsset(destPath, ImportAssetOptions.ForceUpdate);

            // Check this FBX
            CheckFBX(destPath);
        }

        AssetDatabase.Refresh();
        Debug.Log($"Batch import complete. Processed {reports.Count} FBX file(s).");
    }

    private string[] SelectFBXFiles()
    {
        // Use OpenFolderPanel to select a folder containing FBX files, then enumerate .fbx files inside.
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

        // Load the FBX asset
        GameObject fbxAsset = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
        if (fbxAsset == null)
        {
            report.issues.Add("Failed to load the FBX asset.");
            reports.Add(report);
            return;
        }

        // Check 1: Whether the model naming contains default names like "polycylinder"
        CheckModelNaming(fbxAsset, report);

        // Check 2: Whether any part has no material applied
        CheckMaterials(fbxAsset, report);

        reports.Add(report);
    }

    private void CheckModelNaming(GameObject fbxAsset, FBXReport report)
    {
        // Get all children (including those with Mesh Renderers)
        Transform[] allTransforms = fbxAsset.GetComponentsInChildren<Transform>(true);
        List<string> suspiciousNames = new List<string>();

        // Default / suspicious naming patterns from Maya, 3ds Max, Blender, etc.
        string[] suspiciousPatterns = new string[]
        {
            "polycylinder",
            "polycube",
            "polysphere",
            "polytorus",
            "polyplane",
            "polycone",
            "poly",
            "pcube",
            "pcylinder",
            "psphere",
            "ptorus",
            "pplane",
            "pcone",
            "p cube",
            "p cylinder",
            "p sphere",
            "p torus",
            "p plane",
            "p cone",
            "cube",
            "cylinder",
            "sphere",
            "torus",
            "plane",
            "cone",
            "mesh",
            "object",
            "group",
            "null",
            "locator"
        };

        foreach (Transform t in allTransforms)
        {
            if (t == fbxAsset.transform) continue; // Skip the root object

            string name = t.name.ToLower().Trim();

            // Skip empty names
            if (string.IsNullOrEmpty(name)) continue;

            bool isSuspicious = false;
            foreach (string pattern in suspiciousPatterns)
            {
                // Exact match or starts with pattern (e.g., "pCube1", "polyCylinder2")
                if (name == pattern || name.StartsWith(pattern))
                {
                    isSuspicious = true;
                    break;
                }
                // Also catch names like "cube1", "sphere2"
                if (name.StartsWith(pattern) && name.Length > pattern.Length && char.IsDigit(name[pattern.Length]))
                {
                    isSuspicious = true;
                    break;
                }
            }

            if (isSuspicious && !suspiciousNames.Contains(t.name))
                suspiciousNames.Add(t.name);
        }

        if (suspiciousNames.Count > 0)
        {
            report.issues.Add($"Model naming may be non-standard (default-like names): {string.Join(", ", suspiciousNames)}");
        }
    }

    private void CheckMaterials(GameObject fbxAsset, FBXReport report)
    {
        Renderer[] renderers = fbxAsset.GetComponentsInChildren<Renderer>(true);
        if (renderers.Length == 0)
        {
            report.issues.Add("No Renderer components found. This may not be a valid model.");
            return;
        }

        List<string> defaultMaterialObjects = new List<string>();

        foreach (Renderer renderer in renderers)
        {
            Material[] mats = renderer.sharedMaterials;
            if (mats == null || mats.Length == 0)
            {
                defaultMaterialObjects.Add(renderer.gameObject.name);
                continue;
            }

            bool usesDefault = false;
            foreach (Material mat in mats)
            {
                if (mat == null)
                {
                    usesDefault = true;
                    break;
                }

                // Unity 默认漫射材质的名称通常包含 "Default-Diffuse"
                // 同时检查路径以防名称被本地化或修改
                if (mat.name.Contains("Default-Diffuse") ||
                    mat.name.Contains("Default Diffuse") ||
                    AssetDatabase.GetAssetPath(mat).Contains("Default-Diffuse"))
                {
                    usesDefault = true;
                    break;
                }
            }

            if (usesDefault)
                defaultMaterialObjects.Add(renderer.gameObject.name);
        }

        if (defaultMaterialObjects.Count > 0)
        {
            report.issues.Add(
                $"The following objects appear to use Unity's default diffuse material " +
                $"(likely no material in the source FBX): {string.Join(", ", defaultMaterialObjects.Distinct())}"
            );
        }
    }

    private void ShowDetailWindow(FBXReport report)
    {
        // Open a detailed information window
        FBXDetailWindow.ShowWindow(report.fileName, report.issues, report.assetPath);
    }

    // Standalone detail window
    public class FBXDetailWindow : EditorWindow
    {
        private string fileName;
        private List<string> issues;
        private string assetPath;
        private Vector2 scrollPos;

        public static void ShowWindow(string name, List<string> issueList, string path)
        {
            var window = GetWindow<FBXDetailWindow>("FBX Details");
            window.fileName = name;
            window.issues = issueList;
            window.assetPath = path;
            window.minSize = new Vector2(400, 300);
            window.Show();
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField($"File: {fileName}", EditorStyles.boldLabel);
            EditorGUILayout.LabelField($"Path: {assetPath}", EditorStyles.miniLabel);
            EditorGUILayout.Space();

            if (issues == null || issues.Count == 0)
            {
                EditorGUILayout.HelpBox("✅ No issues found. Naming is standard and all materials are applied.", MessageType.Info);
            }
            else
            {
                EditorGUILayout.HelpBox($"⚠️ {issues.Count} issue(s) found:", MessageType.Warning);
                scrollPos = EditorGUILayout.BeginScrollView(scrollPos);
                foreach (var issue in issues)
                {
                    EditorGUILayout.LabelField("• " + issue, EditorStyles.wordWrappedLabel);
                    EditorGUILayout.Space(4);
                }
                EditorGUILayout.EndScrollView();
            }

            EditorGUILayout.Space();
            if (GUILayout.Button("Ping Asset in Project Window", GUILayout.Height(25)))
            {
                var obj = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
                if (obj != null)
                    EditorGUIUtility.PingObject(obj);
            }
        }
    }
}