namespace student
{
    partial class Login_Form
    {
        /// <summary>
        /// Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// Clean up any resources being used.
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
        /// Required method for Designer support - do not modify
        /// the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent()
        {
            UserName_Label = new Label();
            Password_Label = new Label();
            UserName_TextBox = new TextBox();
            Password_TextBox = new TextBox();
            ProgramImage_Iabel = new Label();
            Login_Button = new Button();
            SuspendLayout();
            // 
            // UserName_Label
            // 
            UserName_Label.AutoSize = true;
            UserName_Label.Location = new Point(72, 85);
            UserName_Label.Name = "UserName_Label";
            UserName_Label.Size = new Size(64, 24);
            UserName_Label.TabIndex = 0;
            UserName_Label.Text = "用户名";
            UserName_Label.Click += UserName_Label_Click;
            // 
            // Password_Label
            // 
            Password_Label.AutoSize = true;
            Password_Label.Location = new Point(72, 138);
            Password_Label.Name = "Password_Label";
            Password_Label.Size = new Size(46, 24);
            Password_Label.TabIndex = 1;
            Password_Label.Text = "密码";
            // 
            // UserName_TextBox
            // 
            UserName_TextBox.Location = new Point(142, 82);
            UserName_TextBox.Name = "UserName_TextBox";
            UserName_TextBox.Size = new Size(339, 30);
            UserName_TextBox.TabIndex = 2;
            // 
            // Password_TextBox
            // 
            Password_TextBox.Location = new Point(142, 135);
            Password_TextBox.Name = "Password_TextBox";
            Password_TextBox.Size = new Size(339, 30);
            Password_TextBox.TabIndex = 3;
            // 
            // ProgramImage_Iabel
            // 
            ProgramImage_Iabel.AutoSize = true;
            ProgramImage_Iabel.Font = new Font("Microsoft YaHei UI", 24F, FontStyle.Bold, GraphicsUnit.Point, 134);
            ProgramImage_Iabel.ForeColor = Color.Blue;
            ProgramImage_Iabel.Location = new Point(87, 9);
            ProgramImage_Iabel.Name = "ProgramImage_Iabel";
            ProgramImage_Iabel.Size = new Size(365, 64);
            ProgramImage_Iabel.TabIndex = 4;
            ProgramImage_Iabel.Text = "ImageLabelTS";
            // 
            // Login_Button
            // 
            Login_Button.Location = new Point(183, 187);
            Login_Button.Name = "Login_Button";
            Login_Button.Size = new Size(169, 74);
            Login_Button.TabIndex = 5;
            Login_Button.Text = "登录";
            Login_Button.UseVisualStyleBackColor = true;
            // 
            // Login_Form
            // 
            AutoScaleDimensions = new SizeF(11F, 24F);
            AutoScaleMode = AutoScaleMode.Font;
            ClientSize = new Size(541, 296);
            Controls.Add(Login_Button);
            Controls.Add(ProgramImage_Iabel);
            Controls.Add(Password_TextBox);
            Controls.Add(UserName_TextBox);
            Controls.Add(Password_Label);
            Controls.Add(UserName_Label);
            Name = "Login_Form";
            Text = "登录到ImageLabelTS";
            ResumeLayout(false);
            PerformLayout();
        }

        #endregion

        private Label UserName_Label;
        private Label Password_Label;
        private TextBox UserName_TextBox;
        private TextBox Password_TextBox;
        private Label ProgramImage_Iabel;
        private Button Login_Button;
    }
}