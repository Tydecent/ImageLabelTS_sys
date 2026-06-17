namespace student
{
    partial class MainForm
    {
        /// <summary>
        ///  Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        ///  Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form Designer generated code

        /// <summary>
        ///  Required method for Designer support - do not modify
        ///  the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent()
        {
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(MainForm));
            StatusStrip = new StatusStrip();
            JiuXu_Label = new ToolStripStatusLabel();
            toolStripProgressBar = new ToolStripProgressBar();
            toolStripStatusLabel1 = new ToolStripStatusLabel();
            Status_GroupBox = new GroupBox();
            Login_Button = new Button();
            TaskProgress_Label = new Label();
            TaskProgress_Bar = new ProgressBar();
            LoginUser_Label = new Label();
            Control_GroupBox = new GroupBox();
            Push_Button = new Button();
            Pull_Button = new Button();
            Details_dataGridView = new DataGridView();
            ImageDetails_Label = new Label();
            toolStrip1 = new ToolStrip();
            toolStripSplitButton1 = new ToolStripSplitButton();
            toolStripTextBox1 = new ToolStripTextBox();
            toolStripDropDownButton1 = new ToolStripDropDownButton();
            toolStripTextBox2 = new ToolStripTextBox();
            toolStripDropDownButton2 = new ToolStripDropDownButton();
            Refresh_Button = new Button();
            Column1 = new DataGridViewTextBoxColumn();
            Column2 = new DataGridViewTextBoxColumn();
            Column3 = new DataGridViewTextBoxColumn();
            StatusStrip.SuspendLayout();
            Status_GroupBox.SuspendLayout();
            Control_GroupBox.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)Details_dataGridView).BeginInit();
            toolStrip1.SuspendLayout();
            SuspendLayout();
            // 
            // StatusStrip
            // 
            StatusStrip.ImageScalingSize = new Size(24, 24);
            StatusStrip.Items.AddRange(new ToolStripItem[] { JiuXu_Label, toolStripProgressBar, toolStripStatusLabel1 });
            StatusStrip.Location = new Point(0, 774);
            StatusStrip.Name = "StatusStrip";
            StatusStrip.Size = new Size(759, 31);
            StatusStrip.TabIndex = 1;
            StatusStrip.Text = "statusStrip1";
            // 
            // JiuXu_Label
            // 
            JiuXu_Label.Name = "JiuXu_Label";
            JiuXu_Label.Size = new Size(46, 24);
            JiuXu_Label.Text = "就绪";
            // 
            // toolStripProgressBar
            // 
            toolStripProgressBar.Name = "toolStripProgressBar";
            toolStripProgressBar.Size = new Size(100, 23);
            // 
            // toolStripStatusLabel1
            // 
            toolStripStatusLabel1.Font = new Font("Microsoft YaHei UI", 9F, FontStyle.Italic, GraphicsUnit.Point, 134);
            toolStripStatusLabel1.Name = "toolStripStatusLabel1";
            toolStripStatusLabel1.Size = new Size(226, 24);
            toolStripStatusLabel1.Text = "开发版本 - 不代表最终品质";
            // 
            // Status_GroupBox
            // 
            Status_GroupBox.Controls.Add(Login_Button);
            Status_GroupBox.Controls.Add(TaskProgress_Label);
            Status_GroupBox.Controls.Add(TaskProgress_Bar);
            Status_GroupBox.Controls.Add(LoginUser_Label);
            Status_GroupBox.Location = new Point(19, 58);
            Status_GroupBox.Name = "Status_GroupBox";
            Status_GroupBox.Size = new Size(707, 144);
            Status_GroupBox.TabIndex = 2;
            Status_GroupBox.TabStop = false;
            Status_GroupBox.Text = "总览";
            // 
            // Login_Button
            // 
            Login_Button.Location = new Point(604, 17);
            Login_Button.Name = "Login_Button";
            Login_Button.Size = new Size(97, 33);
            Login_Button.TabIndex = 3;
            Login_Button.Text = "登录";
            Login_Button.UseVisualStyleBackColor = true;
            // 
            // TaskProgress_Label
            // 
            TaskProgress_Label.AutoSize = true;
            TaskProgress_Label.Location = new Point(6, 64);
            TaskProgress_Label.Name = "TaskProgress_Label";
            TaskProgress_Label.Size = new Size(82, 24);
            TaskProgress_Label.TabIndex = 2;
            TaskProgress_Label.Text = "任务进度";
            // 
            // TaskProgress_Bar
            // 
            TaskProgress_Bar.Location = new Point(6, 100);
            TaskProgress_Bar.Name = "TaskProgress_Bar";
            TaskProgress_Bar.Size = new Size(410, 38);
            TaskProgress_Bar.TabIndex = 1;
            // 
            // LoginUser_Label
            // 
            LoginUser_Label.AutoSize = true;
            LoginUser_Label.Location = new Point(6, 26);
            LoginUser_Label.Name = "LoginUser_Label";
            LoginUser_Label.Size = new Size(82, 24);
            LoginUser_Label.TabIndex = 0;
            LoginUser_Label.Text = "登录用户";
            // 
            // Control_GroupBox
            // 
            Control_GroupBox.Controls.Add(Push_Button);
            Control_GroupBox.Controls.Add(Pull_Button);
            Control_GroupBox.Location = new Point(19, 234);
            Control_GroupBox.Name = "Control_GroupBox";
            Control_GroupBox.Size = new Size(707, 115);
            Control_GroupBox.TabIndex = 3;
            Control_GroupBox.TabStop = false;
            Control_GroupBox.Text = "控制";
            // 
            // Push_Button
            // 
            Push_Button.Location = new Point(165, 35);
            Push_Button.Name = "Push_Button";
            Push_Button.Size = new Size(143, 61);
            Push_Button.TabIndex = 1;
            Push_Button.Text = "推送";
            Push_Button.UseVisualStyleBackColor = true;
            // 
            // Pull_Button
            // 
            Pull_Button.Location = new Point(16, 35);
            Pull_Button.Name = "Pull_Button";
            Pull_Button.Size = new Size(143, 61);
            Pull_Button.TabIndex = 0;
            Pull_Button.Text = "拉取";
            Pull_Button.UseVisualStyleBackColor = true;
            // 
            // Details_dataGridView
            // 
            Details_dataGridView.ColumnHeadersHeightSizeMode = DataGridViewColumnHeadersHeightSizeMode.AutoSize;
            Details_dataGridView.Columns.AddRange(new DataGridViewColumn[] { Column1, Column2, Column3 });
            Details_dataGridView.Location = new Point(19, 427);
            Details_dataGridView.Name = "Details_dataGridView";
            Details_dataGridView.RowHeadersWidth = 62;
            Details_dataGridView.Size = new Size(707, 282);
            Details_dataGridView.TabIndex = 4;
            // 
            // ImageDetails_Label
            // 
            ImageDetails_Label.AutoSize = true;
            ImageDetails_Label.Location = new Point(12, 388);
            ImageDetails_Label.Name = "ImageDetails_Label";
            ImageDetails_Label.Size = new Size(82, 24);
            ImageDetails_Label.TabIndex = 5;
            ImageDetails_Label.Text = "图片详情";
            // 
            // toolStrip1
            // 
            toolStrip1.ImageScalingSize = new Size(24, 24);
            toolStrip1.Items.AddRange(new ToolStripItem[] { toolStripSplitButton1, toolStripDropDownButton1, toolStripDropDownButton2 });
            toolStrip1.Location = new Point(0, 0);
            toolStrip1.Name = "toolStrip1";
            toolStrip1.Size = new Size(759, 33);
            toolStrip1.TabIndex = 6;
            toolStrip1.Text = "toolStrip1";
            // 
            // toolStripSplitButton1
            // 
            toolStripSplitButton1.DisplayStyle = ToolStripItemDisplayStyle.Text;
            toolStripSplitButton1.DropDownItems.AddRange(new ToolStripItem[] { toolStripTextBox1 });
            toolStripSplitButton1.ImageTransparentColor = Color.Magenta;
            toolStripSplitButton1.Name = "toolStripSplitButton1";
            toolStripSplitButton1.Size = new Size(67, 28);
            toolStripSplitButton1.Text = "文件";
            // 
            // toolStripTextBox1
            // 
            toolStripTextBox1.Name = "toolStripTextBox1";
            toolStripTextBox1.Size = new Size(100, 30);
            // 
            // toolStripDropDownButton1
            // 
            toolStripDropDownButton1.DisplayStyle = ToolStripItemDisplayStyle.Text;
            toolStripDropDownButton1.DropDownItems.AddRange(new ToolStripItem[] { toolStripTextBox2 });
            toolStripDropDownButton1.Image = (Image)resources.GetObject("toolStripDropDownButton1.Image");
            toolStripDropDownButton1.ImageTransparentColor = Color.Magenta;
            toolStripDropDownButton1.Name = "toolStripDropDownButton1";
            toolStripDropDownButton1.Size = new Size(64, 28);
            toolStripDropDownButton1.Text = "工具";
            // 
            // toolStripTextBox2
            // 
            toolStripTextBox2.Name = "toolStripTextBox2";
            toolStripTextBox2.Size = new Size(100, 30);
            toolStripTextBox2.Text = "检测自交";
            // 
            // toolStripDropDownButton2
            // 
            toolStripDropDownButton2.DisplayStyle = ToolStripItemDisplayStyle.Text;
            toolStripDropDownButton2.Image = (Image)resources.GetObject("toolStripDropDownButton2.Image");
            toolStripDropDownButton2.ImageTransparentColor = Color.Magenta;
            toolStripDropDownButton2.Name = "toolStripDropDownButton2";
            toolStripDropDownButton2.Size = new Size(64, 28);
            toolStripDropDownButton2.Text = "关于";
            // 
            // Refresh_Button
            // 
            Refresh_Button.Location = new Point(623, 388);
            Refresh_Button.Name = "Refresh_Button";
            Refresh_Button.Size = new Size(97, 33);
            Refresh_Button.TabIndex = 4;
            Refresh_Button.Text = "刷新";
            Refresh_Button.UseVisualStyleBackColor = true;
            // 
            // Column1
            // 
            Column1.HeaderText = "图片名称";
            Column1.MinimumWidth = 8;
            Column1.Name = "Column1";
            Column1.Width = 150;
            // 
            // Column2
            // 
            Column2.HeaderText = "本地状态";
            Column2.MinimumWidth = 8;
            Column2.Name = "Column2";
            Column2.Width = 150;
            // 
            // Column3
            // 
            Column3.HeaderText = "远端状态";
            Column3.MinimumWidth = 8;
            Column3.Name = "Column3";
            Column3.Width = 150;
            // 
            // MainForm
            // 
            AutoScaleDimensions = new SizeF(11F, 24F);
            AutoScaleMode = AutoScaleMode.Font;
            ClientSize = new Size(759, 805);
            Controls.Add(Refresh_Button);
            Controls.Add(toolStrip1);
            Controls.Add(ImageDetails_Label);
            Controls.Add(Details_dataGridView);
            Controls.Add(Control_GroupBox);
            Controls.Add(Status_GroupBox);
            Controls.Add(StatusStrip);
            Name = "MainForm";
            Text = "ImageLabelTS.client.GUI";
            StatusStrip.ResumeLayout(false);
            StatusStrip.PerformLayout();
            Status_GroupBox.ResumeLayout(false);
            Status_GroupBox.PerformLayout();
            Control_GroupBox.ResumeLayout(false);
            ((System.ComponentModel.ISupportInitialize)Details_dataGridView).EndInit();
            toolStrip1.ResumeLayout(false);
            toolStrip1.PerformLayout();
            ResumeLayout(false);
            PerformLayout();
        }

        #endregion
        private StatusStrip StatusStrip;
        private ToolStripStatusLabel JiuXu_Label;
        private ToolStripProgressBar toolStripProgressBar;
        private GroupBox Status_GroupBox;
        private Label LoginUser_Label;
        private Label TaskProgress_Label;
        private ProgressBar TaskProgress_Bar;
        private GroupBox Control_GroupBox;
        private Button Pull_Button;
        private ToolStripStatusLabel toolStripStatusLabel1;
        private Button Push_Button;
        private DataGridView Details_dataGridView;
        private Label ImageDetails_Label;
        private ToolStrip toolStrip1;
        private ToolStripSplitButton toolStripSplitButton1;
        private ToolStripTextBox toolStripTextBox1;
        private ToolStripDropDownButton toolStripDropDownButton1;
        private ToolStripDropDownButton toolStripDropDownButton2;
        private ToolStripTextBox toolStripTextBox2;
        private Button Login_Button;
        private Button Refresh_Button;
        private DataGridViewTextBoxColumn Column1;
        private DataGridViewTextBoxColumn Column2;
        private DataGridViewTextBoxColumn Column3;
    }
}
