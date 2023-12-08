import requests, subprocess, re, os, zipfile, json, logging

class Command:
    def __init__(self, str):
        self.cmd = str

    def run(self):
        hndlr = subprocess.Popen(self.cmd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = hndlr.communicate()
        if not hndlr.returncode == 0:
            msg = 'Error while running {}:\n{}'.format(self.cmd, err)
            raise Exception(msg)
        return out

class GitHubAction:
    def parseRemote_(self):
        txt = Command('git config --get remote.origin.url').run().strip()
        m = re.match("git@github.com:(.*)/(.*).git", txt)
        self.url = 'https://api.github.com/repos/{}/{}/artifacts'.format(m.group(1), m.group(2))

    def __init__(self):
        with open('token', 'r') as stream:
            self.token = stream.read()
        self.headers = {
            "Accept":"application/vnd.github.v3+json",
            "Authorization":"Bearer {}".format(self.token)
        }
        self.parseRemote_()

    def getArtifactId(self, SHA):
        resp =  requests.get(url=self.url)
        for artifact in resp.json()['artifacts']:
            if artifact['workflow_run']['head_sha'] == SHA:
                return artifact['id']
            msg = 'No artifacts found for SHA {}'.format(SHA)
        raise Exception(msg)

    def getArtifact(self, id, destination = 'dist'):
        tmp_zip = 'artifacts.zip'
        resp =  requests.get(headers=self.headers, url='{}/{}/zip'.format(self.url, id))
        with open(tmp_zip, 'wb') as stream:
            stream.write(resp.raw)
        with zipfile.ZipFile(tmp_zip, 'r') as zip_ref:
            zip_ref.extractall(destination)
        os.remove(tmp_zip)

def currentPyPi():
    tag = Command('git describe --tags --abbrev=0').run().strip()
    m = re.match("v(.*)", tag)
    version = m.group(1)
    SHA = Command('git rev-list -n 1 {}'.format(tag)).run().strip()   
    return SHA, version

def bumpedVersion():
    with open('MetaData.json', 'r') as stream:
        return json.load(stream)['version']

def main():
    logging.info('checkout master')
    Command('git checkout main').run()
    Command('git pull').run()

    logging.info('get PyPi data')
    pypiSHA, pypiVersion = currentPyPi()
    logging.info('pypiSHA `{}` pypiVersion `{}`'.format(pypiSHA,pypiVersion))

    logging.info('get bumped version')
    version = bumpedVersion()
    logging.info('bumped version `{}`'.format(version))
    if version == pypiVersion:
        msg = "version {} is already the HEAD one to PyPi: update the ./MetaData.json".format(version)
        raise Exception(msg)
    
    logging.info('get current SHA')
    SHA = Command('git rev-parse HEAD').run()
    logging.info('current SHA `{}`'.format(SHA))
    if SHA == pypiSHA:
        msg = "SHA {} hasn't increase since last up-load to PyPi".format(SHA)
        raise Exception(msg)

    logging.info('get artifacts')
    actions = GitHubAction()
    ci_id = actions.getArtifactId(SHA)
    actions.getArtifact(ci_id)

    logging.info('upload to PyPi')
    Command('twine upload dist/*').run()

    logging.info('update tag to v{}'.format(version))
    Command('git tag -a v{0} -m "PyPi version {0}"'.format(version)).run()
    Command('git push --tags').run()

if __name__ == '__main__':
    logging.basicConfig(format='| %(levelname)s | %(message)s', level=logging.DEBUG)
    main()
