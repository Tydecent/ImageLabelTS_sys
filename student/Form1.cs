using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace student
{
    public partial class MainForm : Form
    {
        // ---------- 配置与状态 ----------
        private string serverUrl;
        private string token;
        private string userName;
        private int totalTasks;
        private List<string> assignedImages;
        private Dictionary<string, UploadedDetail> uploadedDetails;

        private class UploadedDetail
        {
            public string hash { get; set; }
            public DateTime last_upload { get; set; }
        }

        // ---------- 构造函数 ----------
        public MainForm()
        {
            InitializeComponent();
            LoadConfiguration();
            UpdateUI(false);
        }

        // ---------- 配置加载 ----------
        private void LoadConfiguration()
        {
            string configPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "config.json");
            if (File.Exists(configPath))
            {
                try
                {
                    var json = File.ReadAllText(configPath);
                    var config = JsonConvert.DeserializeObject<Config>(json);
                    serverUrl = config.server_url;
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"加载配置文件失败: {ex.Message}", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    serverUrl = "http://localhost:12010";
                }
            }
            else
            {
                // 创建默认配置文件
                var config = new Config { server_url = "http://localhost:12010" };
                File.WriteAllText(configPath, JsonConvert.SerializeObject(config, Formatting.Indented));
                serverUrl = config.server_url;
                MessageBox.Show($"未找到配置文件，已创建默认配置在 {configPath}，请修改后重新启动。", "提示", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
        }

        private class Config
        {
            public string server_url { get; set; }
        }

        // ---------- UI 状态更新 ----------
        private void UpdateUI(bool loggedIn)
        {
            LoginUser_Label.Text = loggedIn ? $"用户: {userName}" : "未登录";
            Login_Button.Text = loggedIn ? "切换用户" : "登录";
            Pull_Button.Enabled = loggedIn;
            Push_Button.Enabled = loggedIn;
            Refresh_Button.Enabled = loggedIn;
            if (!loggedIn)
            {
                TaskProgress_Label.Text = "请登录";
                TaskProgress_Bar.Value = 0;
                Details_dataGridView.Rows.Clear();
            }
        }

        // ---------- 登录 / 登出 ----------
        private void Login_Button_Click(object sender, EventArgs e)
        {
            if (!string.IsNullOrEmpty(token))
            {
                Logout();
                return;
            }

            using (var loginForm = new Login_Form(serverUrl))
            {
                var result = loginForm.ShowDialog();
                if (result == DialogResult.OK)
                {
                    token = loginForm.Token;
                    userName = loginForm.UserName;
                    totalTasks = loginForm.TaskCount;
                    UpdateUI(true);
                    _ = RefreshStatusAsync(); // 自动刷新
                }
            }
        }

        private void Logout()
        {
            token = null;
            userName = null;
            totalTasks = 0;
            assignedImages = null;
            uploadedDetails = null;
            UpdateUI(false);
            Details_dataGridView.Rows.Clear();
            TaskProgress_Label.Text = "已登出";
            TaskProgress_Bar.Value = 0;
        }

        // ---------- 拉取任务 ----------
        private async void Pull_Button_Click(object sender, EventArgs e)
        {
            if (string.IsNullOrEmpty(token))
            {
                MessageBox.Show("请先登录", "提示", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            Pull_Button.Enabled = false;
            try
            {
                await PullTaskAsync();
                await RefreshStatusAsync();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"拉取任务失败: {ex.Message}", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                Pull_Button.Enabled = true;
            }
        }

        private async Task PullTaskAsync()
        {
            using (var client = new HttpClient())
            {
                client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);
                var response = await client.GetAsync($"{serverUrl}/pull");
                if (response.IsSuccessStatusCode)
                {
                    // 下载 ZIP
                    var zipStream = await response.Content.ReadAsStreamAsync();
                    string zipPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, $"{userName}_task.zip");
                    using (var fileStream = File.Create(zipPath))
                    {
                        await zipStream.CopyToAsync(fileStream);
                    }

                    // 解压到 workshop
                    string workshopDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "workshop");
                    if (Directory.Exists(workshopDir))
                        Directory.Delete(workshopDir, true);
                    Directory.CreateDirectory(workshopDir);
                    ZipFile.ExtractToDirectory(zipPath, workshopDir);
                    File.Delete(zipPath);

                    // 清理不属于该学生的旧 JSON
                    var status = await GetStatusAsync();
                    if (status != null)
                    {
                        var assignedSet = new HashSet<string>(status.assigned_images.Select(p => Path.GetFileNameWithoutExtension(p)));
                        foreach (var file in Directory.GetFiles(workshopDir, "*.json"))
                        {
                            string baseName = Path.GetFileNameWithoutExtension(file);
                            if (!assignedSet.Contains(baseName))
                                File.Delete(file);
                        }
                    }

                    MessageBox.Show($"任务包已下载并解压到 {workshopDir}", "完成", MessageBoxButtons.OK, MessageBoxIcon.Information);
                }
                else
                {
                    var error = await response.Content.ReadAsStringAsync();
                    throw new Exception($"下载失败 (HTTP {response.StatusCode}): {error}");
                }
            }
        }

        // ---------- 推送标注 ----------
        private async void Push_Button_Click(object sender, EventArgs e)
        {
            if (string.IsNullOrEmpty(token))
            {
                MessageBox.Show("请先登录", "提示", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            Push_Button.Enabled = false;
            try
            {
                await PushTaskAsync();
                await RefreshStatusAsync();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"上传失败: {ex.Message}", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                Push_Button.Enabled = true;
            }
        }

        private async Task PushTaskAsync()
        {
            var status = await GetStatusAsync();
            if (status == null)
                throw new Exception("无法获取服务器状态");

            var remoteDetails = status.uploaded_details ?? new Dictionary<string, UploadedDetail>();
            string workshopDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "workshop");
            if (!Directory.Exists(workshopDir))
            {
                MessageBox.Show("workshop 目录不存在，请先拉取任务", "提示", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            var jsonFiles = Directory.GetFiles(workshopDir, "*.json");
            int uploaded = 0, skipped = 0, failed = 0;

            using (var client = new HttpClient())
            {
                client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

                foreach (var file in jsonFiles)
                {
                    string baseName = Path.GetFileNameWithoutExtension(file);
                    string localHash = ComputeMD5(file);

                    if (remoteDetails.TryGetValue(baseName, out var remote) && remote.hash == localHash)
                    {
                        skipped++;
                        continue;
                    }

                    try
                    {
                        using (var content = new MultipartFormDataContent())
                        {
                            var fileContent = new ByteArrayContent(File.ReadAllBytes(file));
                            fileContent.Headers.ContentType = new MediaTypeHeaderValue("application/json");
                            content.Add(fileContent, "file", Path.GetFileName(file));

                            var response = await client.PostAsync($"{serverUrl}/push", content);
                            var body = await response.Content.ReadAsStringAsync();
                            if (response.IsSuccessStatusCode)
                            {
                                var result = JsonConvert.DeserializeObject<UploadResponse>(body);
                                if (result.status == "ok")
                                    uploaded++;
                                else
                                {
                                    failed++;
                                    MessageBox.Show($"上传 {Path.GetFileName(file)} 失败: {result.message}", "警告", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                                }
                            }
                            else
                            {
                                failed++;
                                MessageBox.Show($"上传 {Path.GetFileName(file)} 失败 (HTTP {response.StatusCode}): {body}", "警告", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        failed++;
                        MessageBox.Show($"上传 {Path.GetFileName(file)} 异常: {ex.Message}", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    }
                }
            }

            MessageBox.Show($"上传完成: 成功 {uploaded} 个, 跳过 {skipped} 个, 失败 {failed} 个", "结果", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }

        // ---------- 刷新状态 ----------
        private async void Refresh_Button_Click(object sender, EventArgs e)
        {
            if (string.IsNullOrEmpty(token))
            {
                MessageBox.Show("请先登录", "提示", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            Refresh_Button.Enabled = false;
            try
            {
                await RefreshStatusAsync();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"刷新状态失败: {ex.Message}", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                Refresh_Button.Enabled = true;
            }
        }

        private async Task RefreshStatusAsync()
        {
            var status = await GetStatusAsync();
            if (status == null) return;

            assignedImages = status.assigned_images;
            uploadedDetails = status.uploaded_details ?? new Dictionary<string, UploadedDetail>();
            totalTasks = status.total;

            // 更新进度
            TaskProgress_Label.Text = $"已完成 {status.uploaded} / {status.total}";
            TaskProgress_Bar.Maximum = status.total;
            TaskProgress_Bar.Value = status.uploaded;

            // 更新 DataGridView
            Details_dataGridView.Rows.Clear();
            string workshopDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "workshop");

            foreach (var image in assignedImages)
            {
                string baseName = Path.GetFileNameWithoutExtension(image);
                string localJsonPath = Path.Combine(workshopDir, baseName + ".json");
                bool localExists = File.Exists(localJsonPath);

                string remoteStatus = uploadedDetails.ContainsKey(baseName)
                    ? $"已上传 {uploadedDetails[baseName].last_upload.ToLocalTime():yyyy-MM-dd HH:mm}"
                    : "未上传";

                Details_dataGridView.Rows.Add(image, localExists ? "本地存在" : "本地缺失", remoteStatus);
            }
        }

        // ---------- 辅助方法 ----------
        private async Task<StatusResponse> GetStatusAsync()
        {
            using (var client = new HttpClient())
            {
                client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);
                var response = await client.GetAsync($"{serverUrl}/status");
                if (response.IsSuccessStatusCode)
                {
                    var json = await response.Content.ReadAsStringAsync();
                    return JsonConvert.DeserializeObject<StatusResponse>(json);
                }
                else
                {
                    var error = await response.Content.ReadAsStringAsync();
                    throw new Exception($"获取状态失败 (HTTP {response.StatusCode}): {error}");
                }
            }
        }

        private string ComputeMD5(string filePath)
        {
            using (var md5 = MD5.Create())
            using (var stream = File.OpenRead(filePath))
            {
                byte[] hash = md5.ComputeHash(stream);
                return BitConverter.ToString(hash).Replace("-", "").ToLower();
            }
        }

        // ---------- 响应模型 ----------
        private class StatusResponse
        {
            public int uploaded { get; set; }
            public int unuploaded { get; set; }
            public int total { get; set; }
            public List<string> assigned_images { get; set; }
            public Dictionary<string, UploadedDetail> uploaded_details { get; set; }
        }

        private class UploadResponse
        {
            public string status { get; set; }
            public string message { get; set; }
        }

        private class ErrorResponse
        {
            public string status { get; set; }
            public string message { get; set; }
        }

        // 启动自交检测脚本
        private void CheckSelfCrossing_toolStripMenuItem_Click(object sender, EventArgs e)
        {
            // 脚本所在目录（例如可执行程序所在目录，可根据实际调整）
            string workingDir = AppDomain.CurrentDomain.BaseDirectory;
            string scriptPath = Path.Combine(workingDir, "Check_LabelMe.ps1");

            // 若脚本不存在可提前报错（可选），否则 PowerShell 窗口会显示错误并暂停等待
            if (!File.Exists(scriptPath))
            {
                throw new FileNotFoundException($"找不到脚本文件: {scriptPath}");
            }

            // 构建 PowerShell 命令：
            // -NoProfile           加快启动，不加载用户配置文件
            // -ExecutionPolicy Bypass  绕过执行策略限制
            // -Command "& '.\Check_label.ps1'; <暂停提示>"
            string arguments =
                "-NoProfile -ExecutionPolicy Bypass -Command \"& '.\\Check_LabelMe.ps1'; " +
                "Write-Host '脚本执行完毕，按回车键退出...'; Read-Host\"";

            var processInfo = new ProcessStartInfo
            {
                FileName = "powershell.exe",          // Windows PowerShell，也可换成 "pwsh" 使用 PowerShell Core
                Arguments = arguments,
                WorkingDirectory = workingDir,
                UseShellExecute = true,               // 使用操作系统 Shell 打开新窗口
                CreateNoWindow = false                // 显示新终端窗口
            };

            try
            {
                Process.Start(processInfo);
            }
            catch (Exception ex)
            {
                // 启动失败时抛出更明确的异常
                throw new InvalidOperationException("无法启动 PowerShell 终端。", ex);
            }
        }

        private async void Update_toolStripMenuItem_Click(object sender, EventArgs e)
        {
            try
            {
                // 1. 读取 config.json 中的更新服务器地址
                string configPath = "config.json";
                if (!File.Exists(configPath))
                {
                    MessageBox.Show("错误：未找到 config.json 配置文件！", "更新失败", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                string jsonContent = File.ReadAllText(configPath);
                using JsonDocument doc = JsonDocument.Parse(jsonContent);
                JsonElement root = doc.RootElement;
                if (!root.TryGetProperty("update_server_url", out JsonElement urlElement))
                {
                    MessageBox.Show("错误：config.json 中未配置 'update_server_url'", "更新失败", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }
                string updateUrl = urlElement.GetString();
                if (string.IsNullOrWhiteSpace(updateUrl))
                {
                    MessageBox.Show("错误：'update_server_url' 为空", "更新失败", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                // 2. 构建脚本下载 URL 与保存路径
                string scriptUrl = updateUrl.TrimEnd('/') + "/update_script";
                string appDir = AppDomain.CurrentDomain.BaseDirectory;
                string zipPath = Path.Combine(appDir, "update.zip");
                string scriptPath = Path.Combine(appDir, "update.ps1");

                // 3. 并行下载更新包与脚本
                using HttpClient client = new HttpClient();
                client.Timeout = TimeSpan.FromMinutes(5);

                Task downloadZip = DownloadFileAsync(client, updateUrl, zipPath);
                Task downloadScript = DownloadFileAsync(client, scriptUrl, scriptPath);
                await Task.WhenAll(downloadZip, downloadScript);

                // 4. 启动更新脚本并立即退出应用
                ProcessStartInfo psi = new ProcessStartInfo
                {
                    FileName = "powershell.exe",
                    Arguments = $"-ExecutionPolicy Bypass -File \"{scriptPath}\"",
                    UseShellExecute = true,
                    WorkingDirectory = appDir
                };
                Process.Start(psi);

                Environment.Exit(0);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"更新失败：{ex.Message}", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        // 辅助方法：流式下载文件到指定路径
        private async Task DownloadFileAsync(HttpClient client, string url, string destinationPath)
        {
            using HttpResponseMessage response = await client.GetAsync(url, HttpCompletionOption.ResponseHeadersRead);
            response.EnsureSuccessStatusCode();

            using FileStream fileStream = new FileStream(destinationPath, FileMode.Create, FileAccess.Write, FileShare.None);
            using Stream contentStream = await response.Content.ReadAsStreamAsync();
            await contentStream.CopyToAsync(fileStream);
        }
    }
}