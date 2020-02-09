# doujinshi-db

Doujinshi renamer, using [doujinshi.org](http://www.doujinshi.org) API

To use, first copy .doujinshi.template.json to .doujinshi.json in same directory or to the home directory.

The database types supported are SQLite, MySQL, Oracle and PostgreSQL, thanks to [Pony ORM](https://github.com/ponyorm/pony/). Set up your database and change the settings in .doujinshi.json. Also set your in, out and fail paths, and any other settings you want. Supported archive types are .zip, .cbz, .rar, and .cbr. Most important is the API setting.

The renamer automatically renames files in the 'in' path from the config file, any matches that don't meet the threshold (also set in config) will need to be checked in the web ui. The web ui is hosted at 127.0.0.1:5000 by default.

Tested mainly with Chrome and Safari, but works in Firefox too. If you're editing the web ui, make sure you disable the browser cache or stuff won't update. *NOT* designed to run on a public server, only locally.

To run the docker container, edit .doujinshi.docker.json and docker-compose.template.yml. Add the API key to the json config file and change the paths in the docker composite file. Then run docker-compose build and docker-compose run.

# Requirements

```
pip3 install rarfile xmltodict requests Pillow pony flask
```

# TODO

- Add way to restart renamer without restarting whole process (back/front)
- Add pagination (back/front)
- Resizing options for better matches on comics/anthologies (back)
- More API tools for manual additions/search (back/front)
- Check to find empty directories in out path (back)
- Check to see if cover in db matches archive cover (back)
- Add custom tags (back/front)

## License

```
Copyright (c) 2013, Rory B. Bellows 
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
* Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright
notice, this list of conditions and the following disclaimer in the
documentation and/or other materials provided with the distribution.
* Neither the name of takeiteasy nor the
names of its contributors may be used to endorse or promote products
derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL RORY B BELLOWS BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```
