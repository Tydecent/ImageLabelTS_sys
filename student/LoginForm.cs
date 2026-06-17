using System;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using Newtonsoft.Json;

namespace student
{
    public partial class Login_Form : Form
    {
        public string Token { get; private set; }
        public string UserName { get; private set; }
        public int TaskCount { get; private set; }

        private readonly string serverUrl;

        public Login_Form(string serverUrl)
        {
            InitializeComponent();
            this.serverUrl = serverUrl;
        }

        private async void Login_Button_Click(object sender, EventArgs e)
        {
            string name = UserName_TextBox.Text.Trim();
            string password = Password_TextBox.Text;

            if (string.IsNullOrEmpty(name) || string.IsNullOrEmpty(password))
            {
                MessageBox.Show("请输入用户名和密码", "提示", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            Login_Button.Enabled = false;
            try
            {
                using (var client = new HttpClient())
                {
                    var loginData = new { name, password };
                    var content = new StringContent(JsonConvert.SerializeObject(loginData), Encoding.UTF8, "application/json");
                    var response = await client.PostAsync($"{serverUrl}/login", content);
                    var responseBody = await response.Content.ReadAsStringAsync();

                    if (response.IsSuccessStatusCode)
                    {
                        var result = JsonConvert.DeserializeObject<LoginResponse>(responseBody);
                        if (result?.status == "ok")
                        {
                            Token = result.token;
                            UserName = name;
                            TaskCount = result.task_count;
                            DialogResult = DialogResult.OK;
                            Close();
                        }
                        else
                        {
                            MessageBox.Show("登录失败: " + result?.message, "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        }
                    }
                    else
                    {
                        try
                        {
                            var error = JsonConvert.DeserializeObject<ErrorResponse>(responseBody);
                            MessageBox.Show("登录失败: " + error.message, "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        }
                        catch
                        {
                            MessageBox.Show($"登录失败 (HTTP {response.StatusCode}): {responseBody}", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"网络错误: {ex.Message}", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                Login_Button.Enabled = true;
            }
        }

        // ---------- 内部模型 ----------
        private class LoginResponse
        {
            public string status { get; set; }
            public string token { get; set; }
            public int task_count { get; set; }
            public string message { get; set; }
        }

        private class ErrorResponse
        {
            public string status { get; set; }
            public string message { get; set; }
        }
    }
}