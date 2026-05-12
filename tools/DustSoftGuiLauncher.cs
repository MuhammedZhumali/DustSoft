using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace DustSoftLauncher
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            string launcherDirectory = AppDomain.CurrentDomain.BaseDirectory;
            string pythonw = Path.Combine(launcherDirectory, ".venv", "Scripts", "pythonw.exe");
            string mainScript = Path.Combine(launcherDirectory, "DustSoft", "src", "main.py");

            if (!File.Exists(pythonw))
            {
                ShowError("Python virtual environment was not found:\n" + pythonw);
                return;
            }

            if (!File.Exists(mainScript))
            {
                ShowError("DustSoft launcher script was not found:\n" + mainScript);
                return;
            }

            try
            {
                Process.Start(
                    new ProcessStartInfo
                    {
                        FileName = pythonw,
                        Arguments = Quote(mainScript) + " gui",
                        WorkingDirectory = launcherDirectory,
                        UseShellExecute = false,
                    }
                );
            }
            catch (Exception ex)
            {
                ShowError("DustSoft GUI could not be started:\n" + ex.Message);
            }
        }

        private static string Quote(string value)
        {
            return "\"" + value.Replace("\"", "\\\"") + "\"";
        }

        private static void ShowError(string message)
        {
            MessageBox.Show(message, "DustSoft GUI", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
