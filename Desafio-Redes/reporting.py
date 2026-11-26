"""Registro persistente de eventos y reportes de la sesion actual."""
import csv
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from statistics import mean

ROOT = Path(__file__).resolve().parent


class Reporter:
    def __init__(self, mode, root=ROOT):
        self.mode = mode
        self.root = Path(root)
        self.session_id = uuid4().hex[:12]
        self.events = []
        self.last_compliance = None
        self.log_path = self.root / 'logs' / f'{mode}_{self.session_id}.log'
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, kind, message, level='INFO', **data):
        record = {'timestamp': datetime.now().astimezone().isoformat(timespec='seconds'),
                  'session': self.session_id, 'mode': self.mode, 'level': level,
                  'kind': kind, 'message': message, **data}
        self.events.append(record)
        with self.log_path.open('a', encoding='utf-8') as log:
            log.write(json.dumps(record, ensure_ascii=False) + '\n')
        print(f"[{record['timestamp']}] [{self.mode}] [{level}] {message}")

    def audit(self, results):
        total = len(results)
        self.last_compliance = round(100 * sum(r['compliant'] for r in results) / total, 2) if total else None
        self.event('audit', f'Auditoria: {self.last_compliance}% de cumplimiento', compliance=self.last_compliance)
        for row in results:
            if not row['compliant']:
                self.event('drift', f"{row['interface']} {row['parameter']}: {row['actual']} -> {row['expected']}", 'WARNING', detail=row)

    def remediation(self, outcomes, verified_results=None):
        for row in outcomes:
            success = row['success']
            self.event('remediation', f"{row['interface']} {row['parameter']}: " + ('corregido y verificado' if success else f"fallo: {row['error']}"), 'INFO' if success else 'ERROR', detail=row)
        if verified_results is not None:
            total = len(verified_results)
            self.last_compliance = round(100 * sum(r['compliant'] for r in verified_results)/total, 2) if total else None
            self.event('verification', f'Cumplimiento posterior: {self.last_compliance}%')

    def summary(self):
        fixes = [e['detail'] for e in self.events if e['kind'] == 'remediation']
        successful = [f for f in fixes if f['success']]
        return {'session': self.session_id, 'mode': self.mode,
                'generated_at': datetime.now().astimezone().isoformat(timespec='seconds'),
                'audit_cycles': sum(e['kind'] == 'audit' for e in self.events),
                'drift_observations': sum(e['kind'] == 'drift' for e in self.events),
                'successful_remediations': len(successful),
                'failed_remediations': len(fixes)-len(successful),
                'remote_configurations': sum(e['kind'] == 'provisioning' for e in self.events),
                'errors': sum(e['level'] == 'ERROR' for e in self.events),
                'mean_verified_remediation_seconds': round(mean(f['seconds'] for f in successful), 4) if successful else None,
                'last_verified_compliance_percent': self.last_compliance}

    def export(self):
        folder = self.root / 'reports'
        folder.mkdir(parents=True, exist_ok=True)
        stem = folder / f'{self.mode}_{self.session_id}'
        summary = self.summary()
        json_path, csv_path = stem.with_suffix('.json'), stem.with_suffix('.csv')
        json_path.write_text(json.dumps({'summary': summary, 'events': self.events}, indent=2, ensure_ascii=False), encoding='utf-8')
        with csv_path.open('w', encoding='utf-8-sig', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['metric', 'value'])
            writer.writerows(summary.items())
        return json_path, csv_path
