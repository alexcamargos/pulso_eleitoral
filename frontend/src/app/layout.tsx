import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pulso Eleitoral — Auditoria Técnica e Reproduzível de Urnas TSE",
  description:
    "Plataforma analítica e de visualização para auditoria pública de logs de urnas eletrônicas brasileiras (TSE), analisando comparecimento pós-17h e taxas de habilitação biométrica.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen flex flex-col bg-slate-50 text-slate-900 antialiased">
        {/* Link de acessibilidade para salto de conteúdo (WCAG 2.1 AA) */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white focus:rounded-lg focus:shadow-lg focus:outline-none"
        >
          Pular para o conteúdo principal
        </a>
        <div className="flex-1 flex flex-col">{children}</div>
      </body>
    </html>
  );
}
